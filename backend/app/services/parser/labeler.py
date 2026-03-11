"""
CLARION — Auto-Labeler & File Router
======================================
Takes any uploaded file, determines what it is, and routes it
to the correct parser (pdf, audio, image, or passes to Larris for video).

This is the entry point your upload router calls.
"""

from pathlib import Path

from app.models.schema import EvidenceItem
from app.services.parser.pdf import parse_pdf
from app.services.parser.audio import parse_audio
from app.services.parser.image import parse_image


# ──────────────────────────────────────────────
#  FILE TYPE DETECTION
# ──────────────────────────────────────────────

PDF_EXTENSIONS = {".pdf"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def detect_file_type(filename: str) -> str:
    """
    Returns: "pdf", "audio", "image", "video", or "unknown"
    """
    suffix = Path(filename).suffix.lower()

    if suffix in PDF_EXTENSIONS:
        return "pdf"
    elif suffix in AUDIO_EXTENSIONS:
        return "audio"
    elif suffix in IMAGE_EXTENSIONS:
        return "image"
    elif suffix in VIDEO_EXTENSIONS:
        return "video"
    else:
        return "unknown"


# ──────────────────────────────────────────────
#  ROUTER — Parse any file
# ──────────────────────────────────────────────

def parse_evidence(
    file_path: str,
    filename: str,
    media_url: str,
) -> EvidenceItem | None:
    """
    Main entry point for the upload router.
    Detects file type and routes to the appropriate parser.

    For video files, returns None — those go to Larris's pipeline.
    The router should handle video separately.

    Args:
        file_path: Local path to the uploaded file
        filename:  Original filename
        media_url: GCS URL where the file is stored

    Returns:
        EvidenceItem for pdf/audio/image, None for video/unknown
    """
    file_type = detect_file_type(filename)

    if file_type == "pdf":
        return parse_pdf(file_path, filename, media_url)

    elif file_type == "audio":
        return parse_audio(file_path, filename, media_url)

    elif file_type == "image":
        return parse_image(file_path, filename, media_url)

    elif file_type == "video":
        # Video files go to Larris's pipeline
        # Return None so the router knows to forward it
        return None

    else:
        # Unknown file type — try treating as PDF, fall back gracefully
        try:
            return parse_pdf(file_path, filename, media_url)
        except Exception:
            return None