from flask import Flask, request, jsonify, send_file
import io
import logging
from werkzeug.utils import secure_filename
from rq import Queue
from redis import Redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import requests, os, time, base64
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# API-only mode: don't serve a frontend. Keep the static folder for saved results.
app = Flask(__name__, static_folder='static')
# Enable CORS so a frontend (hosted on a different origin) can call the API later
CORS(app)
# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting (basic, in-memory/redis-backed depending on config)
limiter = Limiter(key_func=get_remote_address, default_limits=["60 per hour"])
limiter.init_app(app)
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "static/results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Hardening: limit upload size to 16 MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# Allowed image extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Redis + RQ queue used for background processing
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(redis_url)
task_queue = Queue("tryon", connection=redis_conn)

from config import TRYON_API_KEY, TRYON_API_URL

API_KEY = TRYON_API_KEY
# fallback to default URL if not provided
BASE_URL = TRYON_API_URL or os.getenv("TRYON_API_URL", "https://tryon-api.com/api/v1")

def save_as_jpg(upload_file, folder, name_prefix, max_dim=1200, min_dim=512):
    filename = secure_filename(upload_file.filename)
    temp_path = os.path.join(folder, filename)
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
@limiter.limit("20/hour")
def tryon():
    """Enqueue a tryon job and return job id immediately (202)."""
    try:
        person = request.files.get("person_image")
        garment = request.files.get("garment_image")
        if not person or not garment:
            return jsonify({"error": "Missing images"}), 400

        # Basic extension validation
        def allowed(file):
            fn = file.filename or ""
            return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

        if not allowed(person) or not allowed(garment):
            return jsonify({"error": "Invalid file type"}), 400

        # Save files with secure filenames and unique prefixes
        person_path = save_as_jpg(person, UPLOAD_FOLDER, f"person_{int(time.time())}")
        garment_path = save_as_jpg(garment, UPLOAD_FOLDER, f"garment_{int(time.time())}")

        # Enqueue background job
        from tasks import process_tryon_job

        job = task_queue.enqueue(process_tryon_job, person_path, garment_path)
        logger.info(f"Enqueued job {job.id} for person={person_path} garment={garment_path}")

        return jsonify({"status": "accepted", "job_id": job.id}), 202

    except Exception as e:
        logger.exception("Error enqueuing job")
        return jsonify({"error": str(e)}), 500

@app.route("/results/<filename>")
def serve_result(filename):
    return app.send_static_file(os.path.join("results", filename))


@app.route("/status/<job_id>")
def job_status(job_id):
    """Return RQ job status and result (if available)."""
    try:
        from rq.job import Job
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return jsonify({"error": "Job not found"}), 404

    resp = {"id": job.get_id(), "status": job.get_status()}
    if job.is_finished:
        resp["result"] = job.result
    if job.is_failed:
        resp["error"] = str(job.exc_info)
    return jsonify(resp)

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
