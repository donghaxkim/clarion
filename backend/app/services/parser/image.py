"""
CLARION — Image Evidence Parser
=================================
Handles uploaded photos: car damage, accident scenes,
medical images, document photos, etc.

Flow:
  1. Send image directly to Gemini multimodal
  2. Get description, entity extraction, damage assessment
  3. Assemble into EvidenceItem
"""

import json
from pathlib import Path

from app.models.schema import (
    EvidenceItem, EvidenceType, ExtractedContent, MediaRef,
    Entity, SourceLocation, new_id,
)
from app.utils.gemini_client import ask_gemini_multimodal


ANALYSIS_PROMPT = """You are a legal evidence photo analyzer for a litigation support tool.

Analyze this image and return a JSON object with these exact fields:

{
    "description": "Detailed description of what the image shows, written for a legal context.",

    "evidence_category": "vehicle_damage" | "scene_photo" | "medical_image" | "document_photo" | "other",

    "labels": ["relevant", "tags"],

    "entities": [
        {
            "type": "person" | "vehicle" | "location" | "injury" | "object",
            "name": "What it is (e.g., 'Silver 2020 Toyota Camry — rear damage', 'Intersection of Main & 5th')",
            "details": "Additional detail about this entity visible in the image"
        }
    ],

    "damage_assessment": {
        "present": true,
        "severity": "none" | "minor" | "moderate" | "severe",
        "details": "Specific description of visible damage, location on vehicle/body, estimated extent"
    },

    "observations": [
        "Any legally relevant observation (e.g., 'Skid marks visible on road surface', 'Traffic light appears to show red', 'Airbags deployed')"
    ]
}

Be precise and objective. Describe only what you can actually see. Note uncertainty when appropriate.
"""


def parse_image(
    image_path: str,
    filename: str,
    media_url: str,
) -> EvidenceItem:
    """
    Main entry point. Takes an image file, returns structured EvidenceItem.
    """
    evidence_id = new_id()
    image_bytes = Path(image_path).read_bytes()

    # Determine mime type
    suffix = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
    }
    mime_type = mime_map.get(suffix, "image/jpeg")

    # Analyze with Gemini
    raw = ask_gemini_multimodal(
        prompt=ANALYSIS_PROMPT,
        file_bytes=image_bytes,
        mime_type=mime_type,
        temperature=0.1,
    )

    # Parse response
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    analysis = json.loads(cleaned.strip())

    # Build entities
    entities = []
    for ent_data in analysis.get("entities", []):
        entity = Entity(
            type=ent_data["type"],
            name=ent_data["name"],
            mentions=[
                SourceLocation(
                    evidence_id=evidence_id,
                    excerpt=ent_data.get("details", ""),
                )
            ],
        )
        entities.append(entity)

    # Build content
    content = ExtractedContent(
        text=analysis.get("description", ""),
        image_descriptions=[analysis.get("description", "")],
    )

    evidence = EvidenceItem(
        id=evidence_id,
        filename=filename,
        evidence_type=EvidenceType.PHOTO,
        media=MediaRef(
            url=media_url,
            media_type=mime_type,
            description=analysis.get("description"),
        ),
        content=content,
        entities=entities,
        labels=analysis.get("labels", []),
        summary=analysis.get("description"),
    )

    evidence._analysis = analysis
    return evidence