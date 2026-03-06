# env vars, API keys, GCS bucket names
import os
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GCS_BUCKET = os.getenv("GCS_BUCKET", "clarion-uploads")
GCS_ALLOW_LOCAL_FALLBACK = _env_flag("GCS_ALLOW_LOCAL_FALLBACK", default=False)
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VEO_FAST_MODEL = os.getenv("VEO_FAST_MODEL", "veo-3.1-fast-generate-preview")
VEO_FINAL_MODEL = os.getenv("VEO_FINAL_MODEL", "veo-3.1-generate-preview")
VEO_ALLOW_FAKE = _env_flag("VEO_ALLOW_FAKE", default=False)
RECONSTRUCTION_JOB_STORE_PATH = os.getenv("RECONSTRUCTION_JOB_STORE_PATH", ".reconstruction_jobs.json")
LOCAL_ARTIFACTS_DIR = os.getenv("LOCAL_ARTIFACTS_DIR", ".artifacts")
