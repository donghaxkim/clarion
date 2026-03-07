# env vars, API keys, GCS bucket names
import os

from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", GOOGLE_API_KEY).strip()
if GEMINI_API_KEY and not GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
    GOOGLE_API_KEY = GEMINI_API_KEY

GCS_BUCKET = os.getenv("GCS_BUCKET", "clarion-uploads")
GCS_ALLOW_LOCAL_FALLBACK = _env_flag("GCS_ALLOW_LOCAL_FALLBACK", default=False)
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VEO_FAST_MODEL = os.getenv("VEO_FAST_MODEL", "veo-3.1-fast-generate-preview")
VEO_FINAL_MODEL = os.getenv("VEO_FINAL_MODEL", "veo-3.1-generate-preview")
VEO_ALLOW_FAKE = _env_flag("VEO_ALLOW_FAKE", default=False)
RECONSTRUCTION_JOB_STORE_PATH = os.getenv("RECONSTRUCTION_JOB_STORE_PATH", ".reconstruction_jobs.json")
LOCAL_ARTIFACTS_DIR = os.getenv("LOCAL_ARTIFACTS_DIR", ".artifacts")
REPORT_TEXT_MODEL = os.getenv("REPORT_TEXT_MODEL", "gemini-3.1-flash-lite-preview")
REPORT_HELPER_MODEL = os.getenv("REPORT_HELPER_MODEL", "gemini-3.1-flash-lite-preview")
REPORT_IMAGE_MODEL = os.getenv("REPORT_IMAGE_MODEL", "imagen-4.0-generate-001")
REPORT_SEARCH_MODEL = os.getenv("REPORT_SEARCH_MODEL", "gemini-2.5-flash")
REPORT_MAX_IMAGES = _env_int("REPORT_MAX_IMAGES", 3)
REPORT_MAX_RECONSTRUCTIONS = _env_int("REPORT_MAX_RECONSTRUCTIONS", 2)
REPORT_ENABLE_PUBLIC_CONTEXT = _env_flag("REPORT_ENABLE_PUBLIC_CONTEXT", default=True)
REPORT_CONTEXT_CACHE_ENABLED = _env_flag("REPORT_CONTEXT_CACHE_ENABLED", default=True)
REPORT_JOB_STORE_PATH = os.getenv("REPORT_JOB_STORE_PATH", ".report_jobs.json")
