from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models import Citation, ReportBlockType, ReportProvenance


class ReportGenerationPolicy(BaseModel):
    text_model: str
    helper_model: str
    image_model: str
    search_model: str
    enable_public_context: bool = True
    max_images: int = 3
    max_reconstructions: int = 2
    context_cache_enabled: bool = True


class TimelineEvent(BaseModel):
    event_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    narrative: str = Field(min_length=1)
    sort_key: str = Field(min_length=1)
    timestamp_label: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    scene_description: Optional[str] = None
    image_prompt: Optional[str] = None
    reference_image_uris: list[str] = Field(default_factory=list)
    public_context_queries: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class TimelinePlan(BaseModel):
    timeline_events: list[TimelineEvent] = Field(default_factory=list)


class GroundingReview(BaseModel):
    approved: bool = False
    issues: list[str] = Field(default_factory=list)


class CompositionReview(BaseModel):
    approved: bool = False
    issues: list[str] = Field(default_factory=list)


class ContextNote(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    sort_key: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextPlan(BaseModel):
    notes: list[ContextNote] = Field(default_factory=list)


class MediaRequest(BaseModel):
    block_id: str = Field(min_length=1)
    block_type: ReportBlockType
    anchor_block_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sort_key: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    prompt: Optional[str] = None
    scene_description: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    reference_image_uris: list[str] = Field(default_factory=list)


class MediaPlan(BaseModel):
    image_requests: list[MediaRequest] = Field(default_factory=list)
    reconstruction_requests: list[MediaRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_block_types(self) -> MediaPlan:
        self.image_requests = _normalize_media_requests(
            self.image_requests,
            block_type=ReportBlockType.image,
        )
        self.reconstruction_requests = _normalize_media_requests(
            self.reconstruction_requests,
            block_type=ReportBlockType.video,
        )
        return self


class ComposedBlockDraft(BaseModel):
    id: str = Field(min_length=1)
    type: ReportBlockType
    title: Optional[str] = None
    content: Optional[str] = None
    sort_key: str = Field(min_length=1)
    provenance: ReportProvenance = ReportProvenance.evidence
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list)


class ComposerOutput(BaseModel):
    blocks: list[ComposedBlockDraft] = Field(default_factory=list)


class PipelineResult(BaseModel):
    blocks: list[ComposedBlockDraft] = Field(default_factory=list)
    image_requests: list[MediaRequest] = Field(default_factory=list)
    reconstruction_requests: list[MediaRequest] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_block_types(self) -> PipelineResult:
        self.image_requests = _normalize_media_requests(
            self.image_requests,
            block_type=ReportBlockType.image,
        )
        self.reconstruction_requests = _normalize_media_requests(
            self.reconstruction_requests,
            block_type=ReportBlockType.video,
        )
        return self


def _normalize_media_requests(
    requests: list[MediaRequest],
    *,
    block_type: ReportBlockType,
) -> list[MediaRequest]:
    normalized: list[MediaRequest] = []
    for request in requests:
        if request.block_type == block_type:
            normalized.append(request)
            continue
        normalized.append(request.model_copy(update={"block_type": block_type}))
    return normalized
