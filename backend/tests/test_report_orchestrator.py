import asyncio
import json

from app.agents.reporting import AdkReportingPipeline
from app.agents.reporting.progress import (
    NODE_FINAL_COMPOSER,
    NODE_GROUNDING_REVIEWER,
    NODE_MEDIA_PLANNER,
    NODE_TIMELINE_PLANNER,
    PipelinePreviewSnapshot,
    PipelineProgressEvent,
)
from app.agents.reporting.types import (
    ComposerOutput,
    ComposedBlockDraft,
    ContextPlan,
    MediaPlan,
    MediaRequest,
    PipelineResult,
    ReportGenerationPolicy,
    TimelineEvent,
    TimelinePlan,
)
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
    MediaAsset,
    MediaAssetKind,
    ReportBlockState,
    ReportBlockType,
    ReportDocument,
    ReportGenerationJobStatus,
    ReportProvenance,
    ReportStatus,
)
from app.services.generation.job_store import ReportJobStore
from app.services.generation.orchestrator import ReportGenerationOrchestrator


class _RecordingReportJobStore(ReportJobStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.progress_history: list[int] = []

    def create_job(self, *args, **kwargs):
        job = super().create_job(*args, **kwargs)
        self.progress_history.append(job.progress)
        return job

    def publish(self, job_id, **kwargs):
        updated = super().publish(job_id, **kwargs)
        self.progress_history.append(updated.progress)
        return updated


class _FakePipeline:
    async def run(self, *, bundle, report_id, user_id, progress_callback=None):
        del bundle, report_id, user_id
        citation = Citation(source_id="ev-1", provenance=ReportProvenance.evidence)
        timeline = TimelinePlan(
            timeline_events=[
                TimelineEvent(
                    event_id="impact",
                    title="Impact",
                    narrative="Vehicles converge at the intersection.",
                    sort_key="0001",
                    evidence_refs=["ev-1"],
                    citations=[citation],
                    confidence_score=0.8,
                )
            ]
        )
        media_plan = MediaPlan(
            image_requests=[
                MediaRequest(
                    block_id="event-impact-image",
                    block_type=ReportBlockType.image,
                    anchor_block_id="event-impact",
                    title="Impact Still",
                    sort_key="0001.10",
                    citations=[citation],
                    confidence_score=0.8,
                    prompt="Impact still frame",
                    evidence_refs=["ev-1"],
                )
            ],
            reconstruction_requests=[
                MediaRequest(
                    block_id="event-impact-video",
                    block_type=ReportBlockType.video,
                    anchor_block_id="event-impact",
                    title="Impact Reconstruction",
                    sort_key="0001.20",
                    citations=[citation],
                    confidence_score=0.8,
                    scene_description="Two vehicles collide in the intersection.",
                    evidence_refs=["ev-1"],
                )
            ],
        )
        composer = ComposerOutput(
            blocks=[
                ComposedBlockDraft(
                    id="event-impact",
                    type=ReportBlockType.text,
                    title="Impact",
                    content="The collision occurs.",
                    sort_key="0001",
                    provenance=ReportProvenance.evidence,
                    confidence_score=0.8,
                    citations=[citation],
                ),
            ]
        )
        if progress_callback is not None:
            await progress_callback(PipelineProgressEvent.node_started(NODE_TIMELINE_PLANNER))
            await progress_callback(
                PipelineProgressEvent.snapshot_updated(
                    PipelinePreviewSnapshot(timeline_plan=timeline),
                    preview_reason="timeline_plan",
                )
            )
            await progress_callback(
                PipelineProgressEvent.node_completed(NODE_TIMELINE_PLANNER)
            )
            await progress_callback(
                PipelineProgressEvent.node_started(
                    NODE_GROUNDING_REVIEWER,
                    detail="Review pass 1 of 3",
                    attempt=1,
                )
            )
            await progress_callback(
                PipelineProgressEvent.node_completed(
                    NODE_GROUNDING_REVIEWER,
                    detail="Review pass 1 of 3",
                    attempt=1,
                )
            )
            await progress_callback(PipelineProgressEvent.node_started(NODE_MEDIA_PLANNER))
            await progress_callback(
                PipelineProgressEvent.snapshot_updated(
                    PipelinePreviewSnapshot(
                        timeline_plan=timeline,
                        context_plan=ContextPlan(),
                        media_plan=media_plan,
                    ),
                    preview_reason="media_plan",
                )
            )
            await progress_callback(
                PipelineProgressEvent.node_completed(NODE_MEDIA_PLANNER)
            )
            await progress_callback(PipelineProgressEvent.node_started(NODE_FINAL_COMPOSER))
            await progress_callback(
                PipelineProgressEvent.snapshot_updated(
                    PipelinePreviewSnapshot(
                        timeline_plan=timeline,
                        context_plan=ContextPlan(),
                        media_plan=media_plan,
                        composer_output=composer,
                    ),
                    preview_reason="composer_output",
                )
            )
            await progress_callback(
                PipelineProgressEvent.node_completed(NODE_FINAL_COMPOSER)
            )
        return PipelineResult(
            blocks=composer.blocks,
            image_requests=media_plan.image_requests,
            reconstruction_requests=media_plan.reconstruction_requests,
        )


class _MisTypedMediaPipeline:
    async def run(self, *, bundle, report_id, user_id, progress_callback=None):
        del bundle, report_id, user_id, progress_callback
        citation = Citation(source_id="ev-1", provenance=ReportProvenance.evidence)
        return {
            "blocks": [
                {
                    "id": "event-impact",
                    "type": ReportBlockType.text,
                    "title": "Impact",
                    "content": "The collision occurs.",
                    "sort_key": "0001",
                    "provenance": ReportProvenance.evidence,
                    "confidence_score": 0.8,
                    "citations": [citation.model_dump(mode="json")],
                }
            ],
            "image_requests": [
                {
                    "block_id": "event-impact-image",
                    "block_type": ReportBlockType.text,
                    "anchor_block_id": "event-impact",
                    "title": "Impact Still",
                    "sort_key": "0001.10",
                    "citations": [citation.model_dump(mode="json")],
                    "confidence_score": 0.8,
                    "prompt": "Impact still frame",
                    "evidence_refs": ["ev-1"],
                }
            ],
            "reconstruction_requests": [
                {
                    "block_id": "event-impact-video",
                    "block_type": ReportBlockType.text,
                    "anchor_block_id": "event-impact",
                    "title": "Impact Reconstruction",
                    "sort_key": "0001.20",
                    "citations": [citation.model_dump(mode="json")],
                    "confidence_score": 0.8,
                    "scene_description": "Two vehicles collide in the intersection.",
                    "evidence_refs": ["ev-1"],
                }
            ],
            "warnings": [],
        }


class _FailingPipeline:
    async def run(self, *, bundle, report_id, user_id, progress_callback=None):
        del bundle, report_id, user_id
        citation = Citation(source_id="ev-1", provenance=ReportProvenance.evidence)
        timeline = TimelinePlan(
            timeline_events=[
                TimelineEvent(
                    event_id="impact",
                    title="Impact",
                    narrative="Vehicles converge at the intersection.",
                    sort_key="0001",
                    evidence_refs=["ev-1"],
                    citations=[citation],
                    confidence_score=0.8,
                )
            ]
        )

        if progress_callback is not None:
            await progress_callback(PipelineProgressEvent.node_started(NODE_TIMELINE_PLANNER))
            await progress_callback(
                PipelineProgressEvent.snapshot_updated(
                    PipelinePreviewSnapshot(timeline_plan=timeline),
                    preview_reason="timeline_plan",
                )
            )

        raise RuntimeError("synthetic pipeline failure")


class _FailingAdkPipeline(AdkReportingPipeline):
    def __init__(self):
        super().__init__(
            policy=ReportGenerationPolicy(
                text_model="gemini-3-pro-preview",
                helper_model="gemini-3-flash-preview",
                image_model="gemini-3-pro-image-preview",
                search_model="gemini-2.5-flash",
                enable_public_context=False,
                max_images=1,
                max_reconstructions=1,
            )
        )

    async def run(self, *, bundle, report_id, user_id, progress_callback=None):
        del bundle, report_id, user_id, progress_callback
        raise RuntimeError(
            "Failed to parse the parameter timeline_events of function set_model_response"
        )


class _FakeImageGenerator:
    async def generate(self, *, case_id, report_id, block_id, prompt):
        del case_id, report_id, block_id, prompt
        return MediaAsset(
            kind=MediaAssetKind.image,
            uri="gs://test-bucket/report/impact.png",
            generator="gemini-3-pro-image-preview",
            manifest_uri="gs://test-bucket/report/image-manifest.json",
            state=ReportBlockState.ready,
        )


class _FailingImageGenerator:
    async def generate(self, *, case_id, report_id, block_id, prompt):
        del case_id, report_id, block_id, prompt
        raise RuntimeError("image model unavailable")


class _FakeReconstructionService:
    async def generate(self, *, case_id, section_id, scene_description, evidence_refs, reference_image_uris):
        del case_id, section_id, scene_description, evidence_refs, reference_image_uris
        return MediaAsset(
            kind=MediaAssetKind.video,
            uri="gs://test-bucket/report/impact.mp4",
            generator="veo-3.1-generate-preview",
            manifest_uri="gs://test-bucket/report/video-manifest.json",
            state=ReportBlockState.ready,
        )


def _upload_recorder():
    uploads = {}

    def _upload(data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
        uploads[gcs_key] = {"data": data, "content_type": content_type}
        return f"gs://test-bucket/{gcs_key}"

    return uploads, _upload


def _request() -> GenerateReportRequest:
    return GenerateReportRequest(
        bundle=CaseEvidenceBundle(
            case_id="case-777",
            evidence_items=[
                EvidenceItem(
                    evidence_id="ev-1",
                    kind=EvidenceItemType.transcript,
                    summary="The witness saw the collision.",
                )
            ],
        ),
        user_id="user-1",
    )


def test_orchestrator_runs_full_job_and_persists_report_manifest(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    uploads, upload_fn = _upload_recorder()
    report = ReportDocument(report_id="report-1", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FakePipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=upload_fn,
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReportGenerationJobStatus.completed
    assert final.report is not None
    assert final.report.status == ReportStatus.completed
    assert all(block.id != "timeline-overview" for block in final.report.sections)
    assert all(block.type in {ReportBlockType.text, ReportBlockType.image, ReportBlockType.video} for block in final.report.sections)
    assert any(event.event_type == "media.completed" for event in final.events)
    assert any(event.event_type == "job.activity" for event in final.events)
    assert any(event.event_type == "report.preview.updated" for event in final.events)
    assert final.workflow is not None
    assert final.activity is not None
    assert final.workflow.active_node_ids == []

    image_block = next(block for block in final.report.sections if block.id == "event-impact-image")
    video_block = next(block for block in final.report.sections if block.id == "event-impact-video")
    assert image_block.media[0].uri.endswith("impact.png")
    assert video_block.media[0].uri.endswith("impact.mp4")
    assert final.artifacts is not None
    assert final.artifacts.report_url == final.artifacts.report_gcs_uri

    report_key = "reports/case-777/report-1/report.json"
    manifest_key = "reports/case-777/report-1/manifest.json"
    assert report_key in uploads
    assert manifest_key in uploads
    manifest = json.loads(uploads[manifest_key]["data"].decode("utf-8"))
    assert manifest["report_id"] == "report-1"


def test_end_to_end_event_order_streams_blocks_before_media(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-2", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FakePipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=lambda data, gcs_key, content_type="application/octet-stream": f"gs://test/{gcs_key}",
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    event_types = [event.event_type for event in final.events]
    assert event_types.index("report.preview.updated") < event_types.index("timeline.ready")
    assert event_types.index("block.created") < event_types.index("media.completed")
    ReportDocument.model_validate(final.report.model_dump(mode="json"))


def test_orchestrator_normalizes_media_block_types_before_persisting_report(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-typed", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _MisTypedMediaPipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=lambda data, gcs_key, content_type="application/octet-stream": f"gs://test/{gcs_key}",
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.report is not None

    image_block = next(block for block in final.report.sections if block.id == "event-impact-image")
    video_block = next(block for block in final.report.sections if block.id == "event-impact-video")

    assert image_block.type == ReportBlockType.image
    assert image_block.media[0].kind == MediaAssetKind.image
    assert video_block.type == ReportBlockType.video
    assert video_block.media[0].kind == MediaAssetKind.video


def test_orchestrator_progress_never_regresses(tmp_path):
    store = _RecordingReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-3", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FakePipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=lambda data, gcs_key, content_type="application/octet-stream": f"gs://test/{gcs_key}",
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    assert store.progress_history == sorted(store.progress_history)


def test_orchestrator_freezes_progress_when_pipeline_fails(tmp_path):
    store = _RecordingReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-4", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FailingPipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReportGenerationJobStatus.failed
    assert final.progress == 22
    assert final.progress != 100
    assert store.progress_history == sorted(store.progress_history)


def test_orchestrator_keeps_progress_monotonic_when_media_is_omitted(tmp_path):
    store = _RecordingReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-5", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FakePipeline(),
        image_generator=_FailingImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=lambda data, gcs_key, content_type="application/octet-stream": f"gs://test/{gcs_key}",
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReportGenerationJobStatus.completed
    assert final.progress == 100
    assert "event-impact-image omitted: image model unavailable" in final.warnings
    assert all(block.id != "event-impact-image" for block in final.report.sections)
    assert store.progress_history == sorted(store.progress_history)


def test_orchestrator_falls_back_when_adk_pipeline_fails(tmp_path):
    store = _RecordingReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-6", status=ReportStatus.running)
    job = store.create_job(report=report)

    orchestrator = ReportGenerationOrchestrator(
        job_store=store,
        pipeline_factory=lambda **_: _FailingAdkPipeline(),
        image_generator=_FakeImageGenerator(),
        reconstruction_service=_FakeReconstructionService(),
        upload_bytes_fn=lambda data, gcs_key, content_type="application/octet-stream": f"gs://test/{gcs_key}",
    )

    asyncio.run(orchestrator.run_job(job.job_id, _request()))

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReportGenerationJobStatus.completed
    assert final.report is not None
    assert final.report.status == ReportStatus.completed
    assert any(
        warning.startswith("ADK reporting pipeline failed; used deterministic fallback pipeline.")
        for warning in final.report.warnings
    )
    assert store.progress_history == sorted(store.progress_history)
