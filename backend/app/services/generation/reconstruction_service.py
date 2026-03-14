from __future__ import annotations

from uuid import uuid4

from app.config import VEO_ALLOW_FAKE
from app.models import (
    MediaAsset,
    MediaAssetKind,
    QualityMode,
    ReconstructionJobRequest,
    ReportBlockState,
)
from app.services.video.reconstruction import (
    ReconstructionArtifactService,
    VeoClient,
)


class ReconstructionMediaService:
    def __init__(
        self,
        *,
        artifact_service: ReconstructionArtifactService | None = None,
    ):
        self.artifact_service = artifact_service or ReconstructionArtifactService(
            veo_client=VeoClient(allow_fake=VEO_ALLOW_FAKE),
        )

    async def generate(
        self,
        *,
        case_id: str,
        section_id: str,
        scene_description: str,
        evidence_refs: list[str],
        reference_image_uris: list[str],
    ) -> MediaAsset:
        payload = ReconstructionJobRequest(
            case_id=case_id,
            section_id=section_id,
            scene_description=scene_description,
            evidence_refs=evidence_refs,
            reference_image_uris=reference_image_uris[:3],
            duration_sec=4,
            quality_mode=QualityMode.fast_only,
        )
        result = await self.artifact_service.generate_result(
            job_id=f"report-inline-{uuid4().hex}",
            payload=payload,
        )

        return MediaAsset(
            kind=MediaAssetKind.video,
            uri=result.video_gcs_uri,
            generator=result.model_used,
            manifest_uri=result.manifest_gcs_uri,
            state=ReportBlockState.ready,
        )
