# env vars, API keys, GCS bucket names
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GCS_BUCKET = os.getenv("GCS_BUCKET", "clarion-uploads")
