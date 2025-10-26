from flask import Flask, render_template, request, jsonify, send_file
import requests, os, time, base64
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='.')
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "static/results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

API_KEY = os.getenv("TRYON_API_KEY", "ta_a9430047ac43437c82bab051da5eb456")
BASE_URL = os.getenv("TRYON_API_URL", "https://tryon-api.com/api/v1")

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
    return send_file('index.html')

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
