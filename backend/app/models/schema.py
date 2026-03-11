"""
CLARION — Shared Data Schema v2
================================
The contract between all three team members.

RULES:
  - Do NOT add a field unless you will populate it before the demo
  - Do NOT change a model without telling the team
  - All media stored in GCS — schema only holds URLs

Data flow:
  Upload → EvidenceItem (You) → CaseFile (You) → ReportSection stream (Larris) → UI (Person B)

In-memory only (not persisted):
  EvidenceItem._analysis — parsers stash key_facts/timeline_events here for the pipeline.
  Not serialized by Pydantic (intentional). If you persist CaseFile to DB and reload,
  _analysis will be gone. For the hackathon this is fine. For production, use a
  separate FactStore table and link by evidence_id.
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional, Literal, Any
from datetime import datetime
import uuid


def _id() -> str:
    return uuid.uuid4().hex[:12]


def new_id() -> str:
    """Public alias for _id; used by parsers and services."""
    return _id()


# ═══════════════════════════════════════════════
#  PRIMITIVES — Small reusable pieces
# ═══════════════════════════════════════════════

class MediaRef(BaseModel):
    """Reference to a file in GCS. Never embed raw bytes in the schema."""
    url: str
    media_type: str                           # "image/jpeg", "video/mp4", "application/pdf", "audio/mp3"
    description: Optional[str] = None


class SourcePin(BaseModel):
    """
    Points to exactly where a fact lives in the raw evidence.
    This is how citations trace back to source material.
    """
    evidence_id: str                          # which EvidenceItem
    detail: str                               # human-readable: "Page 2, paragraph 3" or "0:42-0:47" or "top-left of image"
    excerpt: Optional[str] = None             # short verbatim snippet


class SourceLocation(BaseModel):
    """
    Parser-friendly location within evidence (page or time range).
    Convert to SourcePin for Citation via to_source_pin().
    """
    evidence_id: str
    page: Optional[int] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    excerpt: Optional[str] = None

    def to_source_pin(self) -> SourcePin:
        if self.page is not None:
            detail = f"Page {self.page}"
        elif self.timestamp_start is not None and self.timestamp_end is not None:
            detail = f"{self.timestamp_start:.1f}-{self.timestamp_end:.1f}s"
        elif self.timestamp_start is not None:
            detail = f"{self.timestamp_start:.1f}s"
        else:
            detail = "Source"
        return SourcePin(evidence_id=self.evidence_id, detail=detail, excerpt=self.excerpt)


# ═══════════════════════════════════════════════
#  STAGE 1 — EVIDENCE IN (Your domain)
# ═══════════════════════════════════════════════

EVIDENCE_TYPES = Literal[
    "police_report",
    "medical_record",
    "witness_statement",
    "photo",
    "dashcam_video",
    "surveillance_video",
    "insurance_document",
    "diagram",
    "other",
]


class EvidenceType(str, Enum):
    """Enum alias for EVIDENCE_TYPES; use .value for schema fields."""
    POLICE_REPORT = "police_report"
    MEDICAL_RECORD = "medical_record"
    WITNESS_STATEMENT = "witness_statement"
    PHOTO = "photo"
    DASHCAM_VIDEO = "dashcam_video"
    SURVEILLANCE_VIDEO = "surveillance_video"
    INSURANCE_DOCUMENT = "insurance_document"
    DIAGRAM = "diagram"
    OTHER = "other"


class SpeakerSegment(BaseModel):
    """One chunk of speech from audio transcription."""
    speaker: str                              # "Speaker 1" or identified name
    start: float                              # seconds
    end: float                                # seconds
    text: str


class VideoFrame(BaseModel):
    """A key frame extracted from video by Larris's pipeline."""
    timestamp: float                          # seconds into the video
    media: MediaRef                           # the extracted frame image in GCS
    description: Optional[str] = None         # AI-generated scene description


class ExtractedContent(BaseModel):
    """
    Everything pulled from a single piece of evidence.
    Only populate what applies — a PDF won't have speaker_segments,
    an audio file won't have text from OCR.
    """
    text: Optional[str] = None
    tables: Optional[list[dict]] = None
    speaker_segments: Optional[list[SpeakerSegment]] = None
    video_frames: Optional[list[VideoFrame]] = None
    image_description: Optional[str] = None


class Entity(BaseModel):
    """
    A person, vehicle, location, or other named thing found in evidence.
    Linked across documents by matching on name/aliases.
    """
    id: str = Field(default_factory=_id)
    type: Literal["person", "vehicle", "location", "date", "injury", "organization"]
    name: str                                 # "Witness 1 — Jane Doe", "Red 2019 Honda Civic"
    aliases: list[str] = []                   # other references to the same entity
    mentions: list[SourceLocation] = []        # where this entity appears in evidence


class EvidenceItem(BaseModel):
    """
    YOUR primary output — one per uploaded file.
    Your parser creates this, Larris reads it.

    In-memory cache (not serialized):
      _analysis: Optional[dict] — parsers set this to a dict with "key_facts",
      "timeline_events", "labels", "summary", etc. Used by citations and report
      generation. Does not survive CaseFile → DB → reload. Production: FactStore.
    """
    id: str = Field(default_factory=_id)
    filename: str
    evidence_type: EVIDENCE_TYPES
    media: MediaRef                           # the original file in GCS
    content: ExtractedContent
    entities: list[Entity] = []
    labels: list[str] = []                    # auto-tags: ["traffic_accident", "rear_end"]
    summary: Optional[str] = None             # one-paragraph AI summary
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # In-memory only; never serialized. Parsers set this; citations/report read it.
    _analysis: Optional[dict[str, Any]] = PrivateAttr(default=None)


# ═══════════════════════════════════════════════
#  STAGE 2 — INTELLIGENCE (Your domain)
# ═══════════════════════════════════════════════

class Citation(BaseModel):
    """Links a report claim back to raw evidence."""
    id: str = Field(default_factory=_id)
    source: SourcePin
    label: str                                # short display text: "Police Report, p.2"


class ContradictionSeverity(str, Enum):
    """Enum alias for contradiction severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Contradiction(BaseModel):
    """Two facts from different sources that conflict."""
    id: str = Field(default_factory=_id)
    severity: Literal["low", "medium", "high"]
    description: str                          # "Police report says northbound, Witness 1 says eastbound"
    source_a: SourcePin
    source_b: SourcePin
    fact_a: str
    fact_b: str


class MissingInfo(BaseModel):
    """A gap in the evidence that could weaken the case."""
    id: str = Field(default_factory=_id)
    severity: Literal["suggestion", "warning", "critical"]
    description: str                          # "No medical imaging for claimed spinal injury"
    recommendation: Optional[str] = None      # "Request MRI records from treating physician"


# ═══════════════════════════════════════════════
#  STAGE 3 — REPORT OUT (Larris's domain)
# ═══════════════════════════════════════════════

BLOCK_TYPES = Literal[
    "heading",
    "text",
    "image",                                  # AI-generated illustration/reconstruction
    "evidence_image",                         # original uploaded photo with annotations
    "video",                                  # AI-generated reconstruction clip
    "timeline",
    "diagram",
    "counter_argument",
]

SectionType = BLOCK_TYPES  # alias for code that imports SectionType


class TimelineEvent(BaseModel):
    """A single event on the zoomable timeline."""
    time_display: str                         # "2:34 PM" or "March 12, 2024"
    sort_key: float                           # unix timestamp for ordering
    title: str
    description: Optional[str] = None
    evidence_ids: list[str] = []              # which evidence items support this


class ReportSection(BaseModel):
    """
    A single block in the generated report.
    The full report = ordered list of these.

    LARRIS generates these.
    PERSON B renders based on block_type.
    Side-panel editor targets by section ID.
    """
    id: str = Field(default_factory=_id)
    block_type: BLOCK_TYPES
    order: int                                # position in report, 0-indexed

    # Content — populate based on block_type
    text: Optional[str] = None                # for heading, text, counter_argument
    heading_level: Optional[int] = None       # 1, 2, or 3 (only for heading blocks)
    media: Optional[MediaRef] = None          # for image, video, diagram, evidence_image
    timeline_events: Optional[list[TimelineEvent]] = None
    annotations: Optional[list[dict]] = None  # for evidence_image: [{"x": 0.5, "y": 0.3, "label": "Point of impact"}]

    # Intelligence
    citations: list[Citation] = []
    contradiction_ids: list[str] = []         # IDs of Contradiction objects relevant to this section
    entity_ids: list[str] = []                # IDs of Entity objects mentioned here


# ═══════════════════════════════════════════════
#  TOP-LEVEL — THE CASE FILE
# ═══════════════════════════════════════════════

class CaseFile(BaseModel):
    """
    The entire case. Stored in DB. Passed between services.
    Everything links by ID — nothing deeply nested.
    """
    id: str = Field(default_factory=_id)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Case info (from intake chat)
    title: Optional[str] = None               # "Smith v. Johnson — Rear-end Collision"
    case_type: Optional[str] = None           # "personal_injury", "property_damage"
    intake_summary: Optional[str] = None      # what the user described in chat

    # Stage 1
    evidence: list[EvidenceItem] = []
    entities: list[Entity] = []               # merged cross-document entities

    # Stage 2
    contradictions: list[Contradiction] = []
    missing_info: list[MissingInfo] = []

    # Stage 3
    report_sections: list[ReportSection] = []

    # Status
    status: Literal["intake", "parsing", "analyzing", "generating", "complete"] = "intake"


# ═══════════════════════════════════════════════
#  STREAMING CONTRACT (SSE: Larris → Person B)
# ═══════════════════════════════════════════════

class StreamEvent(BaseModel):
    """
    What gets sent over SSE during report generation.
    Person B listens and renders blocks in real time.

    Event types:
      section_start    → new block arriving, render skeleton/placeholder
      section_delta    → partial text chunk (typewriter effect)
      section_complete → block fully generated, render final version
      intelligence     → contradiction or missing info detected mid-generation
      status           → case status changed
      error            → something went wrong
      done             → generation finished
    """
    event: Literal[
        "section_start",
        "section_delta",
        "section_complete",
        "intelligence",
        "status",
        "error",
        "done",
    ]

    # For section_start and section_complete
    section: Optional[ReportSection] = None

    # For section_delta
    section_id: Optional[str] = None
    delta_text: Optional[str] = None

    # For intelligence
    contradiction: Optional[Contradiction] = None
    missing: Optional[MissingInfo] = None

    # For status
    status: Optional[str] = None
    progress: Optional[float] = None          # 0.0 to 1.0

    # For error
    message: Optional[str] = None


# ═══════════════════════════════════════════════
#  API CONTRACTS (FastAPI request/response models)
# ═══════════════════════════════════════════════

class UploadResponse(BaseModel):
    """POST /upload returns this after your parser runs."""
    case_id: str
    evidence_item: EvidenceItem
    entities_found: int
    labels: list[str]


class GenerateRequest(BaseModel):
    """POST /generate kicks off report generation."""
    case_id: str
    focus_entities: Optional[list[str]] = None
    include_counter_arguments: bool = True


class EditSectionRequest(BaseModel):
    """POST /edit-section from the side panel chatbot."""
    case_id: str
    section_id: str
    instruction: str                          # "make the speed estimate more conservative"


class EditSectionResponse(BaseModel):
    """POST /edit-section returns the updated block."""
    updated_section: ReportSection
