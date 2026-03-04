# THE shared JSON schema (everyone imports this)
from pydantic import BaseModel
from typing import Literal, Optional
from enum import Enum


class SectionType(str, Enum):
    text = "text"
    image = "image"
    video = "video"
    timeline = "timeline"


class Citation(BaseModel):
    document_id: str
    page: Optional[int] = None


class ReportSection(BaseModel):
    section_type: SectionType
    content_text: Optional[str] = None
    generated_images: list[str] = []   # URLs
    generated_videos: list[str] = []    # URLs
    citations: list[Citation] = []
    confidence_score: float = 0.0
    contradictions: list[str] = []
    counter_arguments: list[str] = []
