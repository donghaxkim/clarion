from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceItemType(str, Enum):
    pdf = "pdf"
    image = "image"
    audio = "audio"
    video = "video"
    transcript = "transcript"
    medical = "medical"
    official_record = "official_record"
    other = "other"


class ReportBlockType(str, Enum):
    text = "text"
    image = "image"
    video = "video"


class ReportProvenance(str, Enum):
    evidence = "evidence"
    public_context = "public_context"


class ReportBlockState(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ReportStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ReportGenerationJobStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    composing = "composing"
    generating_media = "generating_media"
    completed = "completed"
    failed = "failed"


class ReportGenerationPhase(str, Enum):
    queued = "queued"
    intake = "intake"
    timeline_planning = "timeline_planning"
    grounding_review = "grounding_review"
    parallel_planning = "parallel_planning"
    composition = "composition"
    media_generation = "media_generation"
    finalizing = "finalizing"


class ReportGenerationActivityStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class MediaAssetKind(str, Enum):
    image = "image"
    video = "video"


class ReportWorkflowNodeKind(str, Enum):
    agent = "agent"
    worker = "worker"


class ReportWorkflowLane(str, Enum):
    chronology = "chronology"
    review = "review"
    planning = "planning"
    composition = "composition"
    media = "media"
    finalize = "finalize"


class ReportWorkflowEdgeRelation(str, Enum):
    sequence = "sequence"
    loop = "loop"
    parallel = "parallel"


class ReportWorkflowNodeStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class SourceSpan(BaseModel):
    segment_id: Optional[str] = None
    page_number: Optional[int] = Field(default=None, ge=1)
    time_range_ms: Optional[list[int]] = Field(default=None, min_length=2, max_length=2)
    snippet: Optional[str] = None
    uri: Optional[str] = None

    @field_validator("time_range_ms")
    @classmethod
    def validate_time_range(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        start, end = value
        if start < 0 or end < start:
            raise ValueError("time_range_ms must be an ordered, non-negative start/end pair")
        return value


class EvidenceItem(BaseModel):
    evidence_id: str = Field(min_length=1)
    kind: EvidenceItemType
    title: Optional[str] = None
    summary: Optional[str] = None
    extracted_text: Optional[str] = None
    media_uri: Optional[str] = None
    source_uri: Optional[str] = None
    source_spans: list[SourceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class EventCandidate(BaseModel):
    event_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    sort_key: str = Field(min_length=1)
    timestamp_label: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    scene_description: Optional[str] = None
    image_prompt_hint: Optional[str] = None
    reference_image_uris: list[str] = Field(default_factory=list, max_length=3)
    public_context_queries: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("evidence_refs", "reference_image_uris", "public_context_queries")
    @classmethod
    def strip_string_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value and value.strip()]


class EntityMention(BaseModel):
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: Optional[str] = None
    description: Optional[str] = None


class CaseEvidenceBundle(BaseModel):
    case_id: str = Field(min_length=1)
    case_summary: Optional[str] = None
    generation_instructions: Optional[str] = None
    evidence_items: list[EvidenceItem] = Field(min_length=1)
    event_candidates: list[EventCandidate] = Field(default_factory=list)
    entities: list[EntityMention] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    bundle: CaseEvidenceBundle
    user_id: str = Field(default="clarion-user", min_length=1)
    enable_public_context: Optional[bool] = None
    max_images: Optional[int] = Field(default=None, ge=0, le=10)
    max_reconstructions: Optional[int] = Field(default=None, ge=0, le=10)


class Citation(BaseModel):
    source_id: str = Field(min_length=1)
    source_label: Optional[str] = None
    excerpt: Optional[str] = None
    segment_id: Optional[str] = None
    page_number: Optional[int] = Field(default=None, ge=1)
    time_range_ms: Optional[list[int]] = Field(default=None, min_length=2, max_length=2)
    snippet: Optional[str] = None
    uri: Optional[str] = None
    provenance: ReportProvenance = ReportProvenance.evidence

    @field_validator("time_range_ms")
    @classmethod
    def validate_time_range(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        start, end = value
        if start < 0 or end < start:
            raise ValueError("time_range_ms must be an ordered, non-negative start/end pair")
        return value

    @field_validator("source_label", "excerpt", "snippet")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class MediaAsset(BaseModel):
    kind: MediaAssetKind
    uri: str = Field(min_length=1)
    generator: str = Field(min_length=1)
    manifest_uri: Optional[str] = None
    state: ReportBlockState = ReportBlockState.ready


class ReportBlock(BaseModel):
    id: str = Field(min_length=1)
    type: ReportBlockType
    title: Optional[str] = None
    content: Optional[str] = None
    sort_key: str = Field(min_length=1)
    provenance: ReportProvenance = ReportProvenance.evidence
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list)
    media: list[MediaAsset] = Field(default_factory=list)
    state: ReportBlockState = ReportBlockState.ready


class ReportArtifactRefs(BaseModel):
    report_gcs_uri: Optional[str] = None
    report_url: Optional[str] = None
    manifest_gcs_uri: Optional[str] = None


class ReportGenerationActivity(BaseModel):
    phase: ReportGenerationPhase
    status: ReportGenerationActivityStatus = ReportGenerationActivityStatus.running
    label: str = Field(min_length=1)
    detail: Optional[str] = None
    node_id: Optional[str] = None
    active_node_ids: list[str] = Field(default_factory=list)
    attempt: Optional[int] = Field(default=None, ge=1)
    max_attempts: Optional[int] = Field(default=None, ge=1)
    updated_at: datetime


class ReportWorkflowNode(BaseModel):
    node_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: ReportWorkflowNodeKind
    lane: ReportWorkflowLane
    optional: bool = False


class ReportWorkflowEdge(BaseModel):
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation: ReportWorkflowEdgeRelation


class ReportWorkflowNodeState(BaseModel):
    node_id: str = Field(min_length=1)
    status: ReportWorkflowNodeStatus = ReportWorkflowNodeStatus.pending
    detail: Optional[str] = None
    attempt: Optional[int] = Field(default=None, ge=1)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ReportWorkflowState(BaseModel):
    version: str = Field(default="v1", min_length=1)
    nodes: list[ReportWorkflowNode] = Field(default_factory=list)
    edges: list[ReportWorkflowEdge] = Field(default_factory=list)
    node_states: list[ReportWorkflowNodeState] = Field(default_factory=list)
    active_node_ids: list[str] = Field(default_factory=list)


class ReportDocument(BaseModel):
    report_id: str = Field(min_length=1)
    status: ReportStatus = ReportStatus.running
    sections: list[ReportBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: Optional[datetime] = None


class ReportJobEvent(BaseModel):
    event_id: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GenerateReportJobAcceptedResponse(BaseModel):
    job_id: str
    report_id: str
    status_url: str
    stream_url: str
    report_url: str


class ReportGenerationJobStatusResponse(BaseModel):
    job_id: str
    report_id: str
    status: ReportGenerationJobStatus
    progress: int = Field(ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    report: Optional[ReportDocument] = None
    artifacts: Optional[ReportArtifactRefs] = None
    activity: Optional[ReportGenerationActivity] = None
    workflow: Optional[ReportWorkflowState] = None


class ReportGenerationJobRecord(ReportGenerationJobStatusResponse):
    events: list[ReportJobEvent] = Field(default_factory=list)


# Backwards-compatible aliases while the rest of the app catches up.
SectionType = ReportBlockType
ReportSection = ReportBlock
