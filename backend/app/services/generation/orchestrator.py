from __future__ import annotations

import json
from typing import Callable

from app.agents.reporting import build_reporting_pipeline
from app.agents.reporting.types import MediaRequest, PipelineResult
from app.models import (
    GenerateReportRequest,
    ReportArtifactRefs,
    ReportGenerationJobStatus,
)
from app.services.generation.image_generator import GeminiImageGenerator
from app.services.generation.job_store import ReportJobStore
from app.services.generation.reconstruction_service import ReconstructionMediaService
from app.services.generation.report import (
    attach_media_asset,
    create_initial_report,
    drop_block,
    finalize_report,
)
from app.utils.storage import gcs_uri_to_https, upload_bytes


class ReportGenerationOrchestrator:
    def __init__(
        self,
        *,
        job_store: ReportJobStore,
        pipeline_factory: Callable[..., object] = build_reporting_pipeline,
        image_generator: GeminiImageGenerator | None = None,
        reconstruction_service: ReconstructionMediaService | None = None,
        upload_bytes_fn=upload_bytes,
        gcs_uri_to_https_fn=gcs_uri_to_https,
    ):
        self.job_store = job_store
        self.pipeline_factory = pipeline_factory
        self.image_generator = image_generator or GeminiImageGenerator()
        self.reconstruction_service = reconstruction_service or ReconstructionMediaService()
        self.upload_bytes_fn = upload_bytes_fn
        self.gcs_uri_to_https_fn = gcs_uri_to_https_fn

    async def run_job(self, job_id: str, payload: GenerateReportRequest) -> None:
        job = self.job_store.get_job(job_id)
        if job is None or job.report is None:
            raise RuntimeError(f"Unknown report generation job: {job_id}")

        try:
            self.job_store.publish(
                job_id,
                event_type="job.started",
                payload={"report_id": job.report_id},
                status=ReportGenerationJobStatus.planning,
                progress=5,
            )

            pipeline = self.pipeline_factory(
                enable_public_context=payload.enable_public_context,
                max_images=payload.max_images,
                max_reconstructions=payload.max_reconstructions,
            )
            draft = await pipeline.run(
                bundle=payload.bundle,
                report_id=job.report_id,
                user_id=payload.user_id,
            )

            report = create_initial_report(job.report_id, draft)
            self.job_store.publish(
                job_id,
                event_type="timeline.ready",
                payload={
                    "sections": len(report.sections),
                    "warnings": draft.warnings,
                },
                status=ReportGenerationJobStatus.composing,
                progress=25,
                report=report,
            )

            for block in report.sections:
                self.job_store.publish(
                    job_id,
                    event_type="block.created",
                    payload=block.model_dump(mode="json"),
                    report=report,
                )

            report = await self._generate_media(
                job_id=job_id,
                payload=payload,
                report=report,
                draft=draft,
            )
            report = finalize_report(report)
            artifacts = self._persist_report_artifacts(
                case_id=payload.bundle.case_id,
                report=report,
            )
            self.job_store.mark_completed(
                job_id,
                report=report,
                artifacts=artifacts,
            )
        except Exception as exc:
            self.job_store.mark_failed(job_id, _format_exception_message(exc))

    async def _generate_media(
        self,
        *,
        job_id: str,
        payload: GenerateReportRequest,
        report,
        draft: PipelineResult,
    ):
        media_requests = [*draft.image_requests, *draft.reconstruction_requests]
        if not media_requests:
            return report

        total = len(media_requests)
        for index, request in enumerate(media_requests, start=1):
            progress = 40 + int((index - 1) * 45 / max(total, 1))
            self.job_store.publish(
                job_id,
                event_type="media.started",
                payload={"block_id": request.block_id, "type": request.block_type.value},
                status=ReportGenerationJobStatus.generating_media,
                progress=progress,
                report=report,
            )
            try:
                asset = await self._generate_media_asset(
                    payload=payload,
                    request=request,
                    report_id=report.report_id,
                )
                report = attach_media_asset(report, block_id=request.block_id, asset=asset)
                self.job_store.publish(
                    job_id,
                    event_type="block.updated",
                    payload={"block_id": request.block_id, "media": [asset.model_dump(mode="json")]},
                    report=report,
                )
                self.job_store.publish(
                    job_id,
                    event_type="media.completed",
                    payload={"block_id": request.block_id, "uri": asset.uri},
                    progress=progress + 10,
                    report=report,
                )
            except Exception as exc:
                warning = f"{request.block_id} omitted: {exc}"
                report = drop_block(report, block_id=request.block_id, warning=warning)
                self.job_store.publish(
                    job_id,
                    event_type="block.updated",
                    payload={"block_id": request.block_id, "removed": True},
                    warning=warning,
                    report=report,
                )
        return report

    async def _generate_media_asset(
        self,
        *,
        payload: GenerateReportRequest,
        request: MediaRequest,
        report_id: str,
    ):
        if request.block_type.value == "image":
            return await self.image_generator.generate(
                case_id=payload.bundle.case_id,
                report_id=report_id,
                block_id=request.block_id,
                prompt=request.prompt or request.title,
            )

        return await self.reconstruction_service.generate(
            case_id=payload.bundle.case_id,
            section_id=request.block_id,
            scene_description=request.scene_description or request.title,
            evidence_refs=request.evidence_refs or [citation.source_id for citation in request.citations],
            reference_image_uris=request.reference_image_uris,
        )

    def _persist_report_artifacts(self, *, case_id: str, report) -> ReportArtifactRefs:
        base_key = f"reports/{case_id}/{report.report_id}"
        report_gcs_uri = self.upload_bytes_fn(
            report.model_dump_json(indent=2).encode("utf-8"),
            gcs_key=f"{base_key}/report.json",
            content_type="application/json",
        )
        manifest_gcs_uri = self.upload_bytes_fn(
            json.dumps(
                {
                    "report_id": report.report_id,
                    "status": report.status.value,
                    "sections": len(report.sections),
                    "warnings": report.warnings,
                },
                indent=2,
            ).encode("utf-8"),
            gcs_key=f"{base_key}/manifest.json",
            content_type="application/json",
        )
        return ReportArtifactRefs(
            report_gcs_uri=report_gcs_uri,
            report_url=self.gcs_uri_to_https_fn(report_gcs_uri),
            manifest_gcs_uri=manifest_gcs_uri,
        )


def _format_exception_message(exc: BaseException) -> str:
    if not isinstance(exc, BaseExceptionGroup):
        return str(exc)

    messages = [str(exc)]
    for nested in exc.exceptions:
        nested_message = _format_exception_message(nested)
        if nested_message and nested_message not in messages:
            messages.append(nested_message)
    return " | ".join(messages)
