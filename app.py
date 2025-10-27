from flask import Flask, request, jsonify, send_file
import io
from flask_cors import CORS
import requests, os, time, base64
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# API-only mode: don't serve a frontend. Keep the static folder for saved results.
app = Flask(__name__, static_folder='static')
# Enable CORS so a frontend (hosted on a different origin) can call the API later
CORS(app)
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "static/results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

from config import TRYON_API_KEY, TRYON_API_URL

API_KEY = TRYON_API_KEY
# fallback to default URL if not provided
BASE_URL = TRYON_API_URL or os.getenv("TRYON_API_URL", "https://tryon-api.com/api/v1")

def save_as_jpg(upload_file, folder, name_prefix, max_dim=1200, min_dim=512):
    temp_path = os.path.join(folder, upload_file.filename)
    upload_file.save(temp_path)
    img = Image.open(temp_path).convert("RGB")
    
    # Calculate ratios for both min and max constraints
    max_ratio = min(max_dim / max(img.size[0], img.size[1]), 1.0)
    min_ratio = max(min_dim / min(img.size[0], img.size[1]), 1.0)
    
    # Use the larger ratio to ensure minimum size while respecting maximum size
    ratio = max(min_ratio, max_ratio)
    new_size = tuple(int(dim * ratio) for dim in img.size)
    
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    jpg_path = os.path.join(folder, f"{name_prefix}.jpg")
    img.save(jpg_path, format="JPEG", quality=90)
    os.remove(temp_path)
    return jpg_path

@app.route("/")
def home():
    return jsonify({
        "message": "Try-on API is running. Use POST /tryon with form-data fields 'person_image' and 'garment_image' (files).",
        "routes": {
            "/tryon": "POST - form-data: person_image (file), garment_image (file)",
            "/results/<filename>": "GET - retrieve generated result image"
        }
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/download")
def download_url():
    """Proxy-download an image from a public URL and return it as an attachment.

    Usage: GET /download?url=<image_url>
    """
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing 'url' query parameter"}), 400

    try:
        r = requests.get(url, stream=True, timeout=15)
        if r.status_code != 200:
            return jsonify({"error": "Failed to fetch image", "status_code": r.status_code}), 502

        # Try to determine filename from URL
        filename = os.path.basename(url.split("?")[0]) or "download.jpg"
        # Fallback to a generic name if the filename looks invalid
        if not any(filename.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            filename = "download.jpg"

        content_type = r.headers.get("Content-Type", "application/octet-stream")
        return send_file(io.BytesIO(r.content), mimetype=content_type, as_attachment=True, download_name=filename)

    except requests.RequestException as e:
        return jsonify({"error": "Error fetching URL", "details": str(e)}), 502


@app.route("/download/results/<filename>")
def download_local_result(filename):
    """Return a locally saved result image (in `static/results`) as a downloadable attachment."""
    local_path = os.path.join(RESULT_FOLDER, filename)
    if not os.path.exists(local_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(local_path, as_attachment=True, download_name=filename)

@app.route("/tryon", methods=["POST"])
def tryon():
    try:
        person = request.files.get("person_image")
        garment = request.files.get("garment_image")
        if not person or not garment:
            return jsonify({"error": "Missing images"}), 400

        person_path = save_as_jpg(person, UPLOAD_FOLDER, "person")
        garment_path = save_as_jpg(garment, UPLOAD_FOLDER, "garment")

        # Step 1: Submit job
        headers = {"Authorization": f"Bearer {API_KEY}"}
        files = {
            "person_images": open(person_path, "rb"),
            "garment_images": open(garment_path, "rb")
        }
        resp = requests.post(f"{BASE_URL}/tryon", headers=headers, files=files)
        if resp.status_code != 202:
            return jsonify({"error": f"API Error {resp.status_code}", "details": resp.text}), resp.status_code

        job_id = resp.json().get("jobId")
        status_url = f"{BASE_URL}/tryon/status/{job_id}"

        # Step 2: Poll until complete
        for _ in range(20):
            time.sleep(3)
            status_resp = requests.get(status_url, headers=headers)
            data = status_resp.json()
            if data.get("status") == "completed":
                image_url = data.get("imageUrl")
                if image_url:
                    img_data = requests.get(image_url).content
                    output_path = os.path.join(RESULT_FOLDER, f"{job_id}.jpg")
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    return jsonify({
                        "status": "completed",
                        "job_id": job_id,
                        "image_url": image_url,
                        "local_result": f"/results/{job_id}.jpg"
                    })
                else:
                    return jsonify({"error": "No image URL found", "details": data}), 500
            elif data.get("status") == "failed":
                return jsonify({"error": "Job failed", "details": data}), 500

        return jsonify({"error": "Job timeout"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/results/<filename>")
def serve_result(filename):
    return app.send_static_file(os.path.join("results", filename))

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
