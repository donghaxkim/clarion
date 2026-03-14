from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from typing import Callable

from app.agents.reporting import (
    AdkReportingPipeline,
    HeuristicReportingPipeline,
    build_reporting_pipeline,
)
from app.agents.reporting.progress import (
    NODE_IMAGE_GENERATOR,
    NODE_RECONSTRUCTION_GENERATOR,
    NODE_REPORT_FINALIZER,
    PipelineProgressEvent,
    WorkflowProgressTracker,
    build_workflow_state,
)
from app.agents.reporting.types import MediaRequest, PipelineResult
from app.models import (
    GenerateReportRequest,
    ReportGenerationActivity,
    ReportGenerationActivityStatus,
    ReportGenerationPhase,
    ReportArtifactRefs,
    ReportGenerationJobStatus,
)
from app.services.generation.image_generator import GeminiImageGenerator
from app.services.generation.job_store import ReportJobStore
from app.services.generation.progress import ReportProgressPolicy
from app.services.generation.reconstruction_service import ReconstructionMediaService
from app.services.generation.report import (
    attach_media_asset,
    create_preview_report,
    create_initial_report,
    drop_block,
    finalize_report,
)
from app.utils.storage import upload_bytes


def _identity_uri(uri: str) -> str:
    return uri


class ReportGenerationOrchestrator:
    def __init__(
        self,
        *,
        job_store: ReportJobStore,
        pipeline_factory: Callable[..., object] = build_reporting_pipeline,
        image_generator: GeminiImageGenerator | None = None,
        reconstruction_service: ReconstructionMediaService | None = None,
        upload_bytes_fn=upload_bytes,
        storage_uri_fn=_identity_uri,
    ):
        self.job_store = job_store
        self.pipeline_factory = pipeline_factory
        self.image_generator = image_generator or GeminiImageGenerator()
        self.reconstruction_service = reconstruction_service or ReconstructionMediaService()
        self.upload_bytes_fn = upload_bytes_fn
        self.storage_uri_fn = storage_uri_fn
        self.progress_policy = ReportProgressPolicy()

    async def run_job(self, job_id: str, payload: GenerateReportRequest) -> None:
        job = self.job_store.get_job(job_id)
        if job is None or job.report is None:
            raise RuntimeError(f"Unknown report generation job: {job_id}")

        tracker = WorkflowProgressTracker(
            job.workflow
            or build_workflow_state(
                enable_public_context=(
                    payload.enable_public_context
                    if payload.enable_public_context is not None
                    else True
                )
            )
        )

        try:
            report = job.report
            self.job_store.publish(
                job_id,
                event_type="job.started",
                payload={"report_id": job.report_id},
                status=ReportGenerationJobStatus.planning,
                progress=self.progress_policy.intake_started,
                report=report,
                activity=_build_intake_activity(payload),
                workflow=tracker.workflow,
            )

            pipeline = self.pipeline_factory(
                enable_public_context=payload.enable_public_context,
                max_images=payload.max_images,
                max_reconstructions=payload.max_reconstructions,
            )

            async def handle_progress(event: PipelineProgressEvent) -> None:
                nonlocal report
                report = await self._publish_pipeline_progress(
                    job_id=job_id,
                    tracker=tracker,
                    report=report,
                    event=event,
                )

            draft = await self._run_pipeline(
                pipeline,
                bundle=payload.bundle,
                report_id=job.report_id,
                user_id=payload.user_id,
                progress_callback=handle_progress,
            )
            draft = _normalize_pipeline_result(draft)

            report = create_initial_report(job.report_id, draft)
            self.job_store.publish(
                job_id,
                event_type="timeline.ready",
                payload={
                    "sections": len(report.sections),
                    "warnings": draft.warnings,
                },
                status=ReportGenerationJobStatus.composing,
                progress=self.progress_policy.timeline_ready,
                report=report,
                activity=tracker.activity,
                workflow=tracker.workflow,
            )

            for block in report.sections:
                self.job_store.publish(
                    job_id,
                    event_type="block.created",
                    payload=block.model_dump(mode="json"),
                    report=report,
                    activity=tracker.activity,
                    workflow=tracker.workflow,
                )

            report = await self._generate_media(
                job_id=job_id,
                payload=payload,
                report=report,
                draft=draft,
                tracker=tracker,
            )
            report = await self._publish_system_progress(
                job_id=job_id,
                tracker=tracker,
                report=report,
                event=PipelineProgressEvent.node_started(NODE_REPORT_FINALIZER),
                progress=self.progress_policy.finalizing_started,
            )
            report = finalize_report(report)
            artifacts = self._persist_report_artifacts(
                case_id=payload.bundle.case_id,
                report=report,
            )
            report = await self._publish_system_progress(
                job_id=job_id,
                tracker=tracker,
                report=report,
                event=PipelineProgressEvent.node_completed(NODE_REPORT_FINALIZER),
                progress=self.progress_policy.finalizing_ready,
            )
            self.job_store.mark_completed(
                job_id,
                report=report,
                artifacts=artifacts,
            )
        except Exception as exc:
            for node_id in tracker.active_node_ids:
                report = await self._publish_system_progress(
                    job_id=job_id,
                    tracker=tracker,
                    report=report,
                    event=PipelineProgressEvent.node_failed(node_id, detail=str(exc)),
                    progress=None,
                )
            self.job_store.mark_failed(job_id, _format_exception_message(exc))

    async def _generate_media(
        self,
        *,
        job_id: str,
        payload: GenerateReportRequest,
        report,
        draft: PipelineResult,
        tracker: WorkflowProgressTracker,
    ):
        media_requests = [*draft.image_requests, *draft.reconstruction_requests]
        if not media_requests:
            return report

        total = len(media_requests)
        for index, request in enumerate(media_requests, start=1):
            node_id = (
                NODE_IMAGE_GENERATOR
                if request.block_type.value == "image"
                else NODE_RECONSTRUCTION_GENERATOR
            )
            report = await self._publish_system_progress(
                job_id=job_id,
                tracker=tracker,
                report=report,
                event=PipelineProgressEvent.node_started(
                    node_id,
                    detail=_media_detail(request, index=index, total=total),
                ),
                progress=None,
            )
            self.job_store.publish(
                job_id,
                event_type="media.started",
                payload={"block_id": request.block_id, "type": request.block_type.value},
                status=ReportGenerationJobStatus.generating_media,
                report=report,
                activity=tracker.activity,
                workflow=tracker.workflow,
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
                    activity=tracker.activity,
                    workflow=tracker.workflow,
                )
                report = await self._publish_system_progress(
                    job_id=job_id,
                    tracker=tracker,
                    report=report,
                    event=PipelineProgressEvent.node_completed(
                        node_id,
                        detail=_media_detail(request, index=index, total=total),
                    ),
                    progress=self.progress_policy.progress_for_media_processed(
                        processed_count=index,
                        total_count=total,
                    ),
                )
                self.job_store.publish(
                    job_id,
                    event_type="media.completed",
                    payload={"block_id": request.block_id, "uri": asset.uri},
                    progress=self.progress_policy.progress_for_media_processed(
                        processed_count=index,
                        total_count=total,
                    ),
                    report=report,
                    activity=tracker.activity,
                    workflow=tracker.workflow,
                )
            except Exception as exc:
                warning = f"{request.block_id} omitted: {exc}"
                report = drop_block(report, block_id=request.block_id, warning=warning)
                report = await self._publish_system_progress(
                    job_id=job_id,
                    tracker=tracker,
                    report=report,
                    event=PipelineProgressEvent.node_failed(
                        node_id,
                        detail=_media_detail(request, index=index, total=total),
                    ),
                    progress=self.progress_policy.progress_for_media_processed(
                        processed_count=index,
                        total_count=total,
                    ),
                )
                self.job_store.publish(
                    job_id,
                    event_type="block.updated",
                    payload={"block_id": request.block_id, "removed": True},
                    warning=warning,
                    report=report,
                    activity=tracker.activity,
                    workflow=tracker.workflow,
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
            report_url=self.storage_uri_fn(report_gcs_uri),
            manifest_gcs_uri=manifest_gcs_uri,
        )

    async def _run_pipeline(
        self,
        pipeline,
        *,
        bundle,
        report_id: str,
        user_id: str,
        progress_callback,
    ):
        run_signature = inspect.signature(pipeline.run)
        kwargs = {
            "bundle": bundle,
            "report_id": report_id,
            "user_id": user_id,
        }
        if "progress_callback" in run_signature.parameters:
            kwargs["progress_callback"] = progress_callback
        try:
            return await pipeline.run(**kwargs)
        except Exception as exc:
            fallback_pipeline = _build_reporting_fallback_pipeline(pipeline, exc)
            if fallback_pipeline is None:
                raise
            return await fallback_pipeline.run(**kwargs)

    async def _publish_pipeline_progress(
        self,
        *,
        job_id: str,
        tracker: WorkflowProgressTracker,
        report,
        event: PipelineProgressEvent,
    ):
        next_report = report
        workflow, activity, changed_node_ids = tracker.apply_event(event)
        progress = self.progress_policy.progress_for_pipeline_event(event)
        status = _status_for_activity(activity)

        if event.snapshot is not None:
            next_report = create_preview_report(
                report.report_id,
                snapshot=event.snapshot,
                warnings=report.warnings,
            )
            payload = {
                "reason": event.preview_reason,
                "phase": activity.phase.value if activity is not None else None,
                "sections": len(next_report.sections),
                "changed_node_ids": changed_node_ids,
            }
            event_type = "report.preview.updated"
        else:
            payload = _activity_payload(activity, changed_node_ids)
            event_type = "job.activity"

        self.job_store.publish(
            job_id,
            event_type=event_type,
            payload=payload,
            status=status,
            progress=progress,
            report=next_report,
            activity=activity,
            workflow=workflow,
        )
        return next_report

    async def _publish_system_progress(
        self,
        *,
        job_id: str,
        tracker: WorkflowProgressTracker,
        report,
        event: PipelineProgressEvent,
        progress: int | None,
    ):
        workflow, activity, changed_node_ids = tracker.apply_event(event)
        self.job_store.publish(
            job_id,
            event_type="job.activity",
            payload=_activity_payload(activity, changed_node_ids),
            status=_status_for_activity(activity),
            progress=progress,
            report=report,
            activity=activity,
            workflow=workflow,
        )
        return report


def _format_exception_message(exc: BaseException) -> str:
    if not isinstance(exc, BaseExceptionGroup):
        return str(exc)

    messages = [str(exc)]
    for nested in exc.exceptions:
        nested_message = _format_exception_message(nested)
        if nested_message and nested_message not in messages:
            messages.append(nested_message)
    return " | ".join(messages)


def _build_intake_activity(payload: GenerateReportRequest) -> ReportGenerationActivity:
    evidence_count = len(payload.bundle.evidence_items)
    candidate_count = len(payload.bundle.event_candidates)
    return ReportGenerationActivity(
        phase=ReportGenerationPhase.intake,
        status=ReportGenerationActivityStatus.running,
        label="Preparing the report workflow.",
        detail=(
            f"Reviewing {evidence_count} evidence item(s) and "
            f"{candidate_count} candidate event(s)."
        ),
        active_node_ids=[],
        updated_at=datetime.now(UTC),
    )


def _status_for_activity(
    activity: ReportGenerationActivity | None,
) -> ReportGenerationJobStatus:
    if activity is None:
        return ReportGenerationJobStatus.planning
    if activity.phase == ReportGenerationPhase.media_generation:
        return ReportGenerationJobStatus.generating_media
    if activity.phase in {
        ReportGenerationPhase.composition,
        ReportGenerationPhase.finalizing,
    }:
        return ReportGenerationJobStatus.composing
    return ReportGenerationJobStatus.planning


def _activity_payload(
    activity: ReportGenerationActivity | None,
    changed_node_ids: list[str],
) -> dict:
    return {
        "activity": activity.model_dump(mode="json") if activity is not None else None,
        "changed_node_ids": changed_node_ids,
    }


def _media_detail(request: MediaRequest, *, index: int, total: int) -> str:
    kind = "image" if request.block_type.value == "image" else "reconstruction"
    return f"Rendering {kind} {index} of {total}: {request.title}"


def _normalize_pipeline_result(draft: PipelineResult | object) -> PipelineResult:
    if isinstance(draft, PipelineResult):
        return PipelineResult.model_validate(draft.model_dump(mode="json"))
    return PipelineResult.model_validate(draft)


def _build_reporting_fallback_pipeline(
    pipeline: object,
    exc: Exception,
) -> HeuristicReportingPipeline | None:
    if not isinstance(pipeline, AdkReportingPipeline):
        return None

    return HeuristicReportingPipeline(
        policy=pipeline.policy,
        warning_message=(
            "ADK reporting pipeline failed; used deterministic fallback pipeline. "
            f"Original error: {exc}"
        ),
    )
