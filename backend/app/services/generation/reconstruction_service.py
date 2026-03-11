from __future__ import annotations

from app.config import RECONSTRUCTION_JOB_STORE_PATH, VEO_ALLOW_FAKE
from app.models import (
    MediaAsset,
    MediaAssetKind,
    QualityMode,
    ReconstructionJobRequest,
    ReconstructionJobStatus,
    ReportBlockState,
)
from app.services.video.reconstruction import (
    ReconstructionJobStore,
    ReconstructionOrchestrator,
    VeoClient,
)


class ReconstructionMediaService:
    def __init__(
        self,
        *,
        job_store: ReconstructionJobStore | None = None,
        orchestrator: ReconstructionOrchestrator | None = None,
    ):
        self.job_store = job_store or ReconstructionJobStore(path=RECONSTRUCTION_JOB_STORE_PATH)
        self.orchestrator = orchestrator or ReconstructionOrchestrator(
            job_store=self.job_store,
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
            quality_mode=QualityMode.fast_then_final,
        )
        job = self.job_store.create_job()
        await self.orchestrator.run_job(job.job_id, payload)

        final_job = self.job_store.get_job(job.job_id)
        if final_job is None or final_job.status != ReconstructionJobStatus.completed or final_job.result is None:
            message = final_job.error if final_job is not None else "reconstruction job disappeared"
            raise RuntimeError(message or "reconstruction failed")

        return MediaAsset(
            kind=MediaAssetKind.video,
            uri=final_job.result.video_gcs_uri,
            generator=final_job.result.model_used,
            manifest_uri=final_job.result.manifest_gcs_uri,
            state=ReportBlockState.ready,
        )
