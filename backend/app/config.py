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

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", VERTEX_PROJECT_ID).strip()
FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID", GCP_PROJECT_ID).strip()
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)").strip()
GCS_BUCKET = os.getenv("GCS_BUCKET", "clarion-uploads").strip()
GCS_SIGNED_URL_TTL_SECONDS = _env_int("GCS_SIGNED_URL_TTL_SECONDS", 3600)
SIGNED_URL_SERVICE_ACCOUNT_EMAIL = os.getenv(
    "SIGNED_URL_SERVICE_ACCOUNT_EMAIL", ""
).strip()
CLOUD_RUN_REGION = os.getenv("CLOUD_RUN_REGION", VERTEX_LOCATION).strip()
CLOUD_RUN_JOBS_API_BASE_URL = os.getenv(
    "CLOUD_RUN_JOBS_API_BASE_URL", "https://run.googleapis.com"
).strip()
CLOUD_TASKS_PROJECT_ID = os.getenv("CLOUD_TASKS_PROJECT_ID", GCP_PROJECT_ID).strip()
CLOUD_TASKS_LOCATION = os.getenv("CLOUD_TASKS_LOCATION", CLOUD_RUN_REGION).strip()
CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL = os.getenv(
    "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL", ""
).strip()
REPORT_TASK_QUEUE = os.getenv("REPORT_TASK_QUEUE", "clarion-report-jobs").strip()
RECONSTRUCTION_TASK_QUEUE = os.getenv(
    "RECONSTRUCTION_TASK_QUEUE", "clarion-reconstruction-jobs"
).strip()
REPORT_WORKER_JOB_NAME = os.getenv(
    "REPORT_WORKER_JOB_NAME", "clarion-report-worker"
).strip()
RECONSTRUCTION_WORKER_JOB_NAME = os.getenv(
    "RECONSTRUCTION_WORKER_JOB_NAME", "clarion-reconstruction-worker"
).strip()
VEO_FAST_MODEL = os.getenv("VEO_FAST_MODEL", "veo-3.1-fast-generate-preview")
VEO_FINAL_MODEL = os.getenv("VEO_FINAL_MODEL", "veo-3.1-generate-preview")
VEO_ALLOW_FAKE = _env_flag("VEO_ALLOW_FAKE", default=False)
REPORT_TEXT_MODEL = os.getenv("REPORT_TEXT_MODEL", "gemini-3.1-flash-lite-preview")
REPORT_HELPER_MODEL = os.getenv("REPORT_HELPER_MODEL", "gemini-3.1-flash-lite-preview")
REPORT_IMAGE_MODEL = os.getenv("REPORT_IMAGE_MODEL", "imagen-4.0-generate-001")
REPORT_SEARCH_MODEL = os.getenv("REPORT_SEARCH_MODEL", "gemini-2.5-flash")
REPORT_MAX_IMAGES = _env_int("REPORT_MAX_IMAGES", 3)
REPORT_MAX_RECONSTRUCTIONS = _env_int("REPORT_MAX_RECONSTRUCTIONS", 2)
REPORT_ENABLE_PUBLIC_CONTEXT = _env_flag("REPORT_ENABLE_PUBLIC_CONTEXT", default=True)
REPORT_CONTEXT_CACHE_ENABLED = _env_flag("REPORT_CONTEXT_CACHE_ENABLED", default=True)
