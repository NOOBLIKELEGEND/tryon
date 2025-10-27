import os

# Configuration module that centralizes how credentials are loaded.
# Prefer environment variables (e.g. from .env or your deployment platform).
# For local convenience you may create a `secrets.py` file (gitignored) with
# TRYON_API_KEY and TRYON_API_URL values. That file will override env vars.

TRYON_API_KEY = os.getenv("TRYON_API_KEY")
TRYON_API_URL = os.getenv("TRYON_API_URL", "https://tryon-api.com/api/v1")

try:
    # Optional local secrets file (should not be committed)
    import secrets as _secrets
    TRYON_API_KEY = getattr(_secrets, "TRYON_API_KEY", TRYON_API_KEY)
    TRYON_API_URL = getattr(_secrets, "TRYON_API_URL", TRYON_API_URL)
except Exception:
    # No local secrets file present — that's expected in CI / deployed envs.
    pass

def ensure_config():
    """Return a list of missing required values (empty if ok)."""
    missing = []
    if not TRYON_API_KEY:
        missing.append("TRYON_API_KEY")
    return missing
