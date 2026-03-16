from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.report_schema import VisualSceneSpec


class AspectRatio(str, Enum):
    landscape = "16:9"
    portrait = "9:16"


class QualityMode(str, Enum):
    fast_then_final = "fast_then_final"
    fast_only = "fast_only"


class ReconstructionJobStatus(str, Enum):
    queued = "queued"
    running_fast = "running_fast"
    running_final = "running_final"
    uploading = "uploading"
    completed = "completed"
    failed = "failed"


class ReconstructionJobRequest(BaseModel):
    case_id: str = Field(min_length=1)
    section_id: Optional[str] = None
    scene_description: str = Field(min_length=1)
    prompt: Optional[str] = None
    prompt_source: Optional[str] = None
    camera_mode: Optional[str] = None
    evidence_refs: list[str] = Field(min_length=1)
    reference_image_uris: list[str] = Field(default_factory=list, max_length=3)
    visual_scene_spec: Optional[VisualSceneSpec] = None
    duration_sec: int = Field(default=8)
    aspect_ratio: AspectRatio = AspectRatio.landscape
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    quality_mode: QualityMode = QualityMode.fast_then_final

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, refs: list[str]) -> list[str]:
        cleaned = [ref.strip() for ref in refs if ref and ref.strip()]
        if not cleaned:
            raise ValueError("evidence_refs must include at least one non-empty reference")
        return cleaned

    @field_validator("reference_image_uris")
    @classmethod
    def validate_reference_image_uris(cls, uris: list[str]) -> list[str]:
        cleaned = [uri.strip() for uri in uris if uri and uri.strip()]
        if len(cleaned) != len(uris):
            raise ValueError("reference_image_uris cannot include empty values")
        return cleaned

    @field_validator("duration_sec")
    @classmethod
    def validate_duration_sec(cls, value: int) -> int:
        if value not in {4, 6, 8}:
            raise ValueError("duration_sec must be one of: 4, 6, 8")
        return value


class ReconstructionResult(BaseModel):
    video_gcs_uri: str
    video_url: str
    model_used: str
    duration_sec: int
    evidence_refs: list[str] = Field(default_factory=list)
    manifest_gcs_uri: str


class ReconstructionCreateJobResponse(BaseModel):
    job_id: str
    status: ReconstructionJobStatus
    poll_url: str


class ReconstructionJobStatusResponse(BaseModel):
    job_id: str
    status: ReconstructionJobStatus
    progress: int = Field(ge=0, le=100)
    error: Optional[str] = None
    result: Optional[ReconstructionResult] = None
