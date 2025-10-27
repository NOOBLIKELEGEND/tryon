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


