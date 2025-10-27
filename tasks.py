import time, os, requests
from app import API_KEY, BASE_URL, RESULT_FOLDER

# This function runs inside an RQ worker process. It should be idempotent and
# return a serializable result (dict). It saves the final image to RESULT_FOLDER.

def process_tryon_job(person_path, garment_path):
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        files = {
            "person_images": open(person_path, "rb"),
            "garment_images": open(garment_path, "rb")
        }
        resp = requests.post(f"{BASE_URL}/tryon", headers=headers, files=files)
        if resp.status_code != 202:
            return {"status": "error", "code": resp.status_code, "details": resp.text}

        job_id = resp.json().get("jobId")
        status_url = f"{BASE_URL}/tryon/status/{job_id}"

        # Poll until complete
        for _ in range(60):
            time.sleep(2)
            status_resp = requests.get(status_url, headers=headers)
            data = status_resp.json()
            if data.get("status") == "completed":
                image_url = data.get("imageUrl")
                if image_url:
                    img_data = requests.get(image_url).content
                    output_path = os.path.join(RESULT_FOLDER, f"{job_id}.jpg")
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    return {"status": "completed", "job_id": job_id, "image_url": image_url, "local_result": f"/results/{job_id}.jpg"}
                else:
                    return {"status": "error", "details": data}
            elif data.get("status") == "failed":
                return {"status": "failed", "details": data}

        return {"status": "timeout"}

    except Exception as e:
        return {"status": "error", "details": str(e)}
