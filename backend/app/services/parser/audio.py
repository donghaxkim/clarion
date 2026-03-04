"""
CLARION — Audio Transcription Service
=======================================
Handles witness testimony recordings, client voice memos,
and any other audio evidence.

Flow:
  1. Transcribe audio using Google Speech-to-Text (or Whisper as fallback)
  2. Diarize speakers (who said what)
  3. Send transcript to Gemini for entity extraction + analysis
  4. Assemble into EvidenceItem

Supports: .mp3, .wav, .m4a, .ogg, .flac
"""

import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from app.models.schema import (
    EvidenceItem, EvidenceType, ExtractedContent, MediaRef,
    Entity, SourceLocation, SpeakerSegment, new_id,
)
from app.utils.gemini_client import ask_gemini_json, ask_gemini_multimodal


# ──────────────────────────────────────────────
#  STEP 1 — TRANSCRIPTION
# ──────────────────────────────────────────────

def convert_to_wav(audio_path: str) -> str:
    """
    Convert any audio format to WAV for consistent processing.
    Returns path to the WAV file.
    """
    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        [
            "ffmpeg", "-i", audio_path,
            "-ar", "16000",       # 16kHz sample rate (optimal for STT)
            "-ac", "1",           # mono
            "-f", "wav",
            wav_path,
            "-y",                 # overwrite
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


def transcribe_with_gemini(audio_path: str) -> dict:
    """
    Use Gemini's native audio understanding for transcription + diarization.
    This is the simplest approach — Gemini handles both in one call.
    Returns structured transcript with speaker segments.
    """
    audio_bytes = Path(audio_path).read_bytes()

    # Determine mime type
    suffix = Path(audio_path).suffix.lower()
    mime_map = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }
    mime_type = mime_map.get(suffix, "audio/wav")

    prompt = """Transcribe this audio recording completely and accurately.

Return a JSON object with these exact fields:

{
    "full_transcript": "The complete transcript as plain text",
    "segments": [
        {
            "speaker": "Speaker 1",
            "start": 0.0,
            "end": 5.2,
            "text": "What the speaker said in this segment"
        }
    ],
    "speaker_count": 2,
    "speaker_notes": "Any observations about speakers (e.g., 'Speaker 1 appears to be the interviewing officer, Speaker 2 appears to be the witness')"
}

If you can identify distinct speakers, label them Speaker 1, Speaker 2, etc.
If you cannot distinguish speakers, use "Speaker 1" for all segments.
Estimate start/end times as best you can in seconds.
Include every word spoken — do not summarize or skip anything."""

    raw = ask_gemini_multimodal(
        prompt=prompt,
        file_bytes=audio_bytes,
        mime_type=mime_type,
        temperature=0.1,
    )

    # Parse JSON response
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return json.loads(cleaned.strip())


# ──────────────────────────────────────────────
#  STEP 2 — ANALYZE TRANSCRIPT
# ──────────────────────────────────────────────

ANALYSIS_PROMPT = """You are a legal document analyzer for a litigation support tool.

Analyze the following transcript from an audio recording (likely a witness statement,
client interview, or deposition) and return structured JSON.

TRANSCRIPT:
---
{transcript}
---

SPEAKER NOTES: {speaker_notes}

Return a JSON object with these exact fields:

{{
    "summary": "2-3 sentence summary of what was said, focusing on legally relevant facts.",

    "labels": ["list", "of", "tags"],

    "entities": [
        {{
            "type": "person" | "vehicle" | "location" | "date" | "injury" | "organization",
            "name": "Display name",
            "aliases": [],
            "mentions": [
                {{
                    "timestamp_start": 0.0,
                    "timestamp_end": 5.0,
                    "excerpt": "What was said about this entity"
                }}
            ]
        }}
    ],

    "key_facts": [
        {{
            "fact": "A factual claim made in the recording",
            "speaker": "Speaker 1",
            "timestamp_start": 0.0,
            "excerpt": "Verbatim quote",
            "category": "incident_description" | "injury" | "timeline" | "liability" | "witness_account" | "other"
        }}
    ],

    "timeline_events": [
        {{
            "timestamp": "Display format of when the described event happened",
            "description": "What happened",
            "mentioned_at": 0.0
        }}
    ],

    "credibility_notes": "Any observations about consistency, hesitation, contradictions within the testimony itself"
}}
"""


def analyze_transcript(transcript_data: dict) -> dict:
    """
    Send transcript to Gemini for entity extraction and legal analysis.
    """
    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript_data["full_transcript"],
        speaker_notes=transcript_data.get("speaker_notes", "No speaker notes available"),
    )

    return ask_gemini_json(
        prompt=prompt,
        system_instruction=(
            "You are a precise legal transcript analyzer. "
            "Extract facts exactly as stated by speakers. "
            "Note any inconsistencies or hedging language."
        ),
        temperature=0.1,
    )


# ──────────────────────────────────────────────
#  STEP 3 — ASSEMBLE INTO SCHEMA
# ──────────────────────────────────────────────

def build_evidence_item(
    filename: str,
    media_url: str,
    transcript_data: dict,
    analysis: dict,
) -> EvidenceItem:
    """
    Combine transcription + analysis into a schema-compliant EvidenceItem.
    """
    evidence_id = new_id()

    # Build speaker segments
    segments = [
        SpeakerSegment(
            speaker=seg["speaker"],
            start=seg["start"],
            end=seg["end"],
            text=seg["text"],
        )
        for seg in transcript_data.get("segments", [])
    ]

    # Build entities
    entities = []
    for ent_data in analysis.get("entities", []):
        entity = Entity(
            type=ent_data["type"],
            name=ent_data["name"],
            aliases=ent_data.get("aliases", []),
            mentions=[
                SourceLocation(
                    evidence_id=evidence_id,
                    timestamp_start=m.get("timestamp_start"),
                    timestamp_end=m.get("timestamp_end"),
                    excerpt=m.get("excerpt"),
                )
                for m in ent_data.get("mentions", [])
            ],
        )
        entities.append(entity)

    # Build content
    content = ExtractedContent(
        text=transcript_data["full_transcript"],
        speaker_segments=segments,
    )

    # Determine evidence type
    evidence_type = EvidenceType.WITNESS_STATEMENT

    evidence = EvidenceItem(
        id=evidence_id,
        filename=filename,
        evidence_type=evidence_type,
        media=MediaRef(
            url=media_url,
            media_type=_get_audio_mime(filename),
        ),
        content=content,
        entities=entities,
        labels=analysis.get("labels", []),
        summary=analysis.get("summary"),
    )

    evidence._analysis = analysis
    return evidence


def _get_audio_mime(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(suffix, "audio/mpeg")


# ──────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────

def parse_audio(
    audio_path: str,
    filename: str,
    media_url: str,
) -> EvidenceItem:
    """
    Main entry point. Takes an audio file path, returns a structured EvidenceItem.

    Args:
        audio_path: Local path to the uploaded audio file
        filename:   Original filename from the user
        media_url:  GCS URL where the original audio is stored

    Returns:
        EvidenceItem ready to be added to the CaseFile
    """
    # Step 1: Transcribe with speaker diarization
    transcript_data = transcribe_with_gemini(audio_path)

    # Step 2: Analyze transcript
    analysis = analyze_transcript(transcript_data)

    # Step 3: Assemble
    evidence = build_evidence_item(
        filename=filename,
        media_url=media_url,
        transcript_data=transcript_data,
        analysis=analysis,
    )

    return evidence


def get_key_facts(evidence: EvidenceItem) -> list[dict]:
    """Retrieve key facts for the intelligence layer."""
    if hasattr(evidence, '_analysis') and evidence._analysis:
        return evidence._analysis.get("key_facts", [])
    return []


def get_timeline_events(evidence: EvidenceItem) -> list[dict]:
    """Retrieve timeline events for the report generator."""
    if hasattr(evidence, '_analysis') and evidence._analysis:
        return evidence._analysis.get("timeline_events", [])
    return []