# Try-On API (API-only)

This repository contains a Flask API that wraps a try-on service. The project no longer serves a frontend; use Postman or curl to test the endpoints.

## Endpoints

- `POST /tryon` — Submit a try-on job.
  - Content type: `multipart/form-data`
  - Form fields:
    - `person_image` (file) — photo of the person
    - `garment_image` (file) — garment image
  - Response: JSON with `status`, `job_id`, `image_url` (external), and `local_result` (path under `/results/`).

- `GET /results/<filename>` — Retrieve a generated result image saved in `static/results/`.

- `GET /` — Returns a small JSON message describing the API.

## Test with Postman

1. Create a new request in Postman.
2. Set method to `POST` and URL to `http://localhost:5000/tryon` (or your deployed URL).
3. Under the `Body` tab, select `form-data`.
4. Add two fields:
   - Key: `person_image`, Type: `File`, select a person image file.
   - Key: `garment_image`, Type: `File`, select a garment image file.
5. Send the request. You should receive JSON with job status and result links.

## Test with curl

```bash
curl -X POST http://localhost:5000/tryon \
  -F "person_image=@/path/to/person.jpg" \
  -F "garment_image=@/path/to/garment.jpg"
```

## Downloading images

There are two ways to download images from the API:

1. Download a saved local result (saved to `static/results/`):

  - URL: `GET /download/results/<filename>`
  - Example (curl):

```bash
curl -O -J http://localhost:5000/download/results/<filename>
```

2. Proxy-download a remote/public image by URL (the API will fetch it and return it as an attachment):

  - URL: `GET /download?url=<image_url>`
  - Example (curl):

```bash
curl -G --output downloaded.jpg "http://localhost:5000/download" --data-urlencode "url=https://example.com/image.jpg"
```

These endpoints are useful for forcing a browser to download the image or for saving it from the API server.

## Running in production (recommended small steps)

Quick production checklist implemented in this repo:

- Background processing with RQ/Redis (enqueue jobs with `/tryon`, worker runs `tasks.process_tryon_job`).
- Container support via `Dockerfile` and `docker-compose.yml` (includes `redis` and a `worker` service).
- Basic rate limiting (flask-limiter) and MAX_CONTENT_LENGTH upload cap.

To run locally with Docker Compose (recommended for production-like testing):

```bash
# set your API key env var or create a .env with TRYON_API_KEY
docker-compose up --build

# web will be on http://localhost:8000
# worker will start and connect to redis
```

Notes:
- On PaaS platforms (Render, Heroku) set `TRYON_API_KEY` and `TRYON_API_URL` as environment variables. If you use background workers on those platforms, configure a separate worker service and a Redis add-on.
- The app still writes results to `static/results/` which is ephemeral on many PaaS; for production use replace this with S3 or another object store and update `tasks.process_tryon_job` accordingly.

## Notes

- Keep API keys out of the repository. Set `TRYON_API_KEY` and `TRYON_API_URL` as environment variables locally or in your deployment platform.
- The server saves results under `static/results/` so they can be fetched with `GET /results/<filename>`.
 
## Integrating a frontend later

- The API enables CORS (all origins) so a browser-based frontend can call the endpoints directly. You can tighten this in production by passing `origins=[...]` to `CORS()`.
- Frontend contract:
  - POST `/tryon` (multipart/form-data) — returns JSON containing `job_id`, `status`, `image_url` and `local_result` (path under `/results/`).
  - GET `/results/<filename>` — returns the generated image.
- Recommended flow for frontend:
  1. Upload person and garment images to `/tryon`.
  2. Poll the API response `image_url` or use the returned `job_id` and implement server-side polling if needed.
  3. Display the final image from the `image_url` or `/results/<filename>`.

If you'd like, I can add a minimal example React or vanilla JS snippet that calls the API (including CORS-friendly fetch examples).

## Keeping credentials private

You have two supported ways to keep credentials (API keys, URLs) out of source control:

1. Environment variables (recommended)
  - Create a `.env` file locally with the variables:

```
TRYON_API_KEY=ta_your_real_api_key_here
TRYON_API_URL=https://tryon-api.com/api/v1
```

  - `.env` is already in `.gitignore` so it won't be committed. The app uses `python-dotenv` to load `.env` during local development.

2. Local `secrets.py` (optional)
  - Copy `secrets.example.py` to `secrets.py` and fill in your values.
  - `secrets.py` is gitignored by default. The app's `config.py` will import `secrets.py` if present and override environment variables.

Make sure you never commit `.env`, `secrets.py`, or any file containing real credentials to your Git repository.


