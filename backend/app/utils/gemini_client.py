"""
CLARION — Gemini Client Helper
================================
Shared Gemini API wrapper. Both parser (You) and generation (Larris) import this.
Handles initialization, retries, and structured JSON output.
"""

from google import genai
from google.genai import types
import json
import os
import time


# ──────────────────────────────────────────────
#  CLIENT INITIALIZATION
# ──────────────────────────────────────────────

def get_client() -> genai.Client:
    """
    Initialize Gemini client.
    Uses GOOGLE_API_KEY env var or Application Default Credentials on GCP.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    else:
        # On Google Cloud, uses ADC automatically
        return genai.Client()


# Default model — use Gemini 2.5 Flash for speed during parsing,
# switch to Pro for report generation if needed.
FAST_MODEL = "gemini-2.5-flash-preview-05-20"
FULL_MODEL = "gemini-2.5-pro-preview-05-06"


# ──────────────────────────────────────────────
#  STRUCTURED OUTPUT HELPERS
# ──────────────────────────────────────────────

def ask_gemini(
    prompt: str,
    model: str = FAST_MODEL,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_retries: int = 3,
) -> str:
    """
    Simple text prompt → text response.
    Low temperature for factual extraction.
    """
    client = get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            raise e


def ask_gemini_json(
    prompt: str,
    model: str = FAST_MODEL,
    system_instruction: str | None = None,
    temperature: float = 0.1,
    max_retries: int = 3,
) -> dict:
    """
    Prompt Gemini and parse response as JSON.
    Adds explicit JSON instruction to the prompt.
    Lower temperature for consistent structured output.
    """
    json_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown, no backticks, no explanation. Just the JSON object."""

    raw = ask_gemini(
        prompt=json_prompt,
        model=model,
        system_instruction=system_instruction,
        temperature=temperature,
        max_retries=max_retries,
    )

    # Clean common issues
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    return json.loads(cleaned)


def ask_gemini_multimodal(
    prompt: str,
    file_bytes: bytes,
    mime_type: str,
    model: str = FAST_MODEL,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_retries: int = 3,
) -> str:
    """
    Send a file (image, PDF, audio, video) along with a text prompt.
    Used for analyzing uploaded evidence directly.
    """
    client = get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    contents = [
        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        prompt,
    ]

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise e