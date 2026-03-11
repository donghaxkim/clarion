import asyncio
import json

from app.agents.reporting.types import ComposedBlockDraft, MediaRequest, PipelineResult
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


class _FakePipeline:
    async def run(self, *, bundle, report_id, user_id):
        del bundle, report_id, user_id
        citation = Citation(source_id="ev-1", provenance=ReportProvenance.evidence)
        return PipelineResult(
            blocks=[
                ComposedBlockDraft(
                    id="timeline-overview",
                    type=ReportBlockType.timeline,
                    title="Overview",
                    content="Approach\nImpact",
                    sort_key="0000",
                    provenance=ReportProvenance.evidence,
                    confidence_score=0.9,
                    citations=[citation],
                ),
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
            ],
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
    assert any(event.event_type == "media.completed" for event in final.events)

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
    assert event_types.index("block.created") < event_types.index("media.completed")
    ReportDocument.model_validate(final.report.model_dump(mode="json"))
