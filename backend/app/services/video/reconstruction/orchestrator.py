from __future__ import annotations

import json
from datetime import UTC, datetime

from app.config import VEO_FAST_MODEL, VEO_FINAL_MODEL
from app.models import (
    QualityMode,
    ReconstructionJobRequest,
    ReconstructionJobStatus,
    ReconstructionResult,
)
from app.services.video.reconstruction.job_store import ReconstructionJobStore
from app.services.video.reconstruction.prompt_builder import (
    build_fallback_prompt,
    build_prompt,
    build_refined_prompt,
)
from app.services.video.reconstruction.veo_client import VeoClient
from app.utils.storage import upload_bytes


def _identity_uri(uri: str) -> str:
    return uri


class ReconstructionOrchestrator:
    def __init__(
        self,
        *,
        job_store: ReconstructionJobStore,
        veo_client: VeoClient,
        upload_bytes_fn=upload_bytes,
        storage_uri_fn=_identity_uri,
    ):
        self.job_store = job_store
        self.veo_client = veo_client
        self.upload_bytes_fn = upload_bytes_fn
        self.storage_uri_fn = storage_uri_fn

    async def run_job(self, job_id: str, payload: ReconstructionJobRequest) -> None:
        try:
            model_used, video_bytes = await self._generate_video(job_id, payload)
            result = self._upload_result(job_id, payload, model_used, video_bytes)
            self.job_store.mark_completed(job_id, result)
        except Exception as exc:
            self.job_store.mark_failed(job_id, str(exc))

    async def _generate_video(
        self, job_id: str, payload: ReconstructionJobRequest
    ) -> tuple[str, bytes]:
        self._set_status(job_id, ReconstructionJobStatus.running_fast, 20)
        fast_video = await self._generate_with_retry(
            model=VEO_FAST_MODEL,
            prompt=build_prompt(payload),
            payload=payload,
        )
        if payload.quality_mode == QualityMode.fast_only:
            return VEO_FAST_MODEL, fast_video

        self._set_status(job_id, ReconstructionJobStatus.running_final, 60)
        final_video = await self._generate_with_retry(
            model=VEO_FINAL_MODEL,
            prompt=build_refined_prompt(payload),
            payload=payload,
        )
        return VEO_FINAL_MODEL, final_video

    def _upload_result(
        self,
        job_id: str,
        payload: ReconstructionJobRequest,
        model_used: str,
        video_bytes: bytes,
    ) -> ReconstructionResult:
        self._set_status(job_id, ReconstructionJobStatus.uploading, 85)
        base_key = f"reconstructions/{payload.case_id}/{job_id}"

        video_gcs_uri = self.upload_bytes_fn(
            video_bytes,
            gcs_key=f"{base_key}/video.mp4",
            content_type="video/mp4",
        )
        manifest_gcs_uri = self.upload_bytes_fn(
            json.dumps(
                self._build_manifest(
                    job_id=job_id,
                    payload=payload,
                    model_used=model_used,
                    video_gcs_uri=video_gcs_uri,
                ),
                indent=2,
            ).encode("utf-8"),
            gcs_key=f"{base_key}/manifest.json",
            content_type="application/json",
        )

        return ReconstructionResult(
            video_gcs_uri=video_gcs_uri,
            video_url=self.storage_uri_fn(video_gcs_uri),
            model_used=model_used,
            duration_sec=payload.duration_sec,
            evidence_refs=payload.evidence_refs,
            manifest_gcs_uri=manifest_gcs_uri,
        )

    async def _generate_with_retry(
        self, *, model: str, prompt: str, payload: ReconstructionJobRequest
    ) -> bytes:
        options = self._generation_options(payload)
        try:
            return await self.veo_client.generate_video(model=model, prompt=prompt, **options)
        except Exception as primary_error:
            fallback_prompt = build_fallback_prompt(payload)
            try:
                return await self.veo_client.generate_video(
                    model=model,
                    prompt=fallback_prompt,
                    **options,
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    "Veo generation failed after retry "
                    f"(primary={type(primary_error).__name__}: {primary_error}; "
                    f"fallback={type(fallback_error).__name__}: {fallback_error})"
                ) from fallback_error

    def _set_status(
        self, job_id: str, status: ReconstructionJobStatus, progress: int
    ) -> None:
        self.job_store.update_status(job_id, status=status, progress=progress, error=None)

    @staticmethod
    def _generation_options(payload: ReconstructionJobRequest) -> dict[str, object]:
        return {
            "duration_sec": payload.duration_sec,
            "aspect_ratio": payload.aspect_ratio.value,
            "reference_image_uris": payload.reference_image_uris,
            "negative_prompt": payload.negative_prompt,
            "seed": payload.seed,
        }

    @staticmethod
    def _build_manifest(
        *,
        job_id: str,
        payload: ReconstructionJobRequest,
        model_used: str,
        video_gcs_uri: str,
    ) -> dict[str, object]:
        return {
            "job_id": job_id,
            "case_id": payload.case_id,
            "section_id": payload.section_id,
            "status": ReconstructionJobStatus.completed.value,
            "model_used": model_used,
            "duration_sec": payload.duration_sec,
            "aspect_ratio": payload.aspect_ratio.value,
            "evidence_refs": payload.evidence_refs,
            "reference_image_uris": payload.reference_image_uris,
            "video_gcs_uri": video_gcs_uri,
            "created_at": datetime.now(UTC).isoformat(),
        }
