from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
    MediaAsset,
    MediaAssetKind,
    ReportArtifactRefs,
    ReportBlock,
    ReportBlockState,
    ReportDocument,
    ReportGenerationJobStatus,
    ReportProvenance,
    ReportStatus,
)
from app.routers import generate
from app.services.generation.job_store import ReportJobStore


class _RecordingDispatcher:
    def __init__(self):
        self.job_ids: list[str] = []

    def dispatch_report_job(self, job_id: str) -> str:
        self.job_ids.append(job_id)
        return f"report-{job_id}"


def _payload():
    return {
        "bundle": {
            "case_id": "case-router",
            "evidence_items": [
                {
                    "evidence_id": "ev-1",
                    "kind": "transcript",
                    "summary": "Witness statement",
                }
            ],
        },
        "user_id": "user-1",
    }


def test_create_report_job_returns_202(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)

    client = TestClient(app)
    response = client.post("/generate/jobs", json=_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["stream_url"] == f"/generate/jobs/{body['job_id']}/stream"

    stored = store.get_job(body["job_id"])
    assert stored is not None
    assert stored.status == ReportGenerationJobStatus.queued
    assert stored.activity is not None
    assert stored.workflow is not None
    assert dispatcher.job_ids == [body["job_id"]]
    saved_request = store.load_request(body["job_id"])
    assert saved_request.user_id == "user-1"


def test_stream_and_report_endpoints_return_job_events(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)
    monkeypatch.setattr(
        generate,
        "materialize_browser_uri",
        lambda uri, *, base_url=None: (
            None if uri is None else uri.replace("gs://", "https://signed.test/")
        ),
    )

    report = ReportDocument(
        report_id="report-router",
        status=ReportStatus.running,
        sections=[
            ReportBlock(
                id="impact-image",
                type="image",
                title="Impact Still",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                citations=[
                    Citation(
                        source_id="ev-1",
                        segment_id="seg-1",
                        excerpt="The witness saw the impact in the intersection.",
                        provenance=ReportProvenance.evidence,
                        uri="gs://test-bucket/evidence/ev-1.pdf",
                    )
                ],
                media=[
                    MediaAsset(
                        kind=MediaAssetKind.image,
                        uri="gs://test-bucket/reports/report-router/media/impact.png",
                        generator="gemini-image",
                        manifest_uri="gs://test-bucket/reports/report-router/media/impact.manifest.json",
                        state=ReportBlockState.ready,
                    )
                ],
            )
        ],
    )
    job = store.create_job(report=report)
    store.publish(
        job.job_id,
        event_type="job.started",
        payload={"report_id": report.report_id},
        status=ReportGenerationJobStatus.planning,
        progress=10,
        report=report,
    )
    completed_report = report.model_copy(update={"status": ReportStatus.completed})
    store.mark_completed(
        job.job_id,
        report=completed_report,
        artifacts=ReportArtifactRefs(
            report_gcs_uri="gs://test-bucket/reports/report-router/report.json",
            report_url="gs://test-bucket/reports/report-router/report.json",
            manifest_gcs_uri="gs://test-bucket/reports/report-router/manifest.json",
        ),
    )

    client = TestClient(app)
    stream_response = client.get(f"/generate/jobs/{job.job_id}/stream")
    assert stream_response.status_code == 200
    assert "event: job.started" in stream_response.text
    assert "event: job.completed" in stream_response.text

    job_response = client.get(f"/generate/jobs/{job.job_id}")
    assert job_response.status_code == 200
    job_body = job_response.json()
    assert job_body["artifacts"]["report_url"] == "https://signed.test/test-bucket/reports/report-router/report.json"
    assert "activity" in job_body
    assert "workflow" in job_body
    assert (
        job_body["report"]["sections"][0]["media"][0]["uri"]
        == "https://signed.test/test-bucket/reports/report-router/media/impact.png"
    )
    assert (
        job_body["report"]["sections"][0]["citations"][0]["uri"]
        == "https://signed.test/test-bucket/evidence/ev-1.pdf"
    )

    report_response = client.get(f"/generate/reports/{report.report_id}")
    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["report_id"] == report.report_id
    assert (
        report_body["sections"][0]["media"][0]["manifest_uri"]
        == "https://signed.test/test-bucket/reports/report-router/media/impact.manifest.json"
    )


def test_report_endpoints_return_500_when_signing_fails(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)

    def _raise_materialization_error(uri, *, base_url=None):
        del uri, base_url
        raise RuntimeError("signing failed")

    monkeypatch.setattr(
        generate,
        "materialize_browser_uri",
        _raise_materialization_error,
    )

    report = ReportDocument(
        report_id="report-router",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="impact-image",
                type="image",
                title="Impact Still",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                citations=[
                    Citation(
                        source_id="ev-1",
                        provenance=ReportProvenance.evidence,
                        uri="gs://test-bucket/evidence/ev-1.pdf",
                    )
                ],
                media=[
                    MediaAsset(
                        kind=MediaAssetKind.image,
                        uri="gs://test-bucket/reports/report-router/media/impact.png",
                        generator="gemini-image",
                        manifest_uri="gs://test-bucket/reports/report-router/media/impact.manifest.json",
                        state=ReportBlockState.ready,
                    )
                ],
            )
        ],
    )
    job = store.create_job(report=report)
    store.mark_completed(
        job.job_id,
        report=report,
        artifacts=ReportArtifactRefs(
            report_gcs_uri="gs://test-bucket/reports/report-router/report.json",
            report_url="gs://test-bucket/reports/report-router/report.json",
            manifest_gcs_uri="gs://test-bucket/reports/report-router/manifest.json",
        ),
    )

    client = TestClient(app)

    job_response = client.get(f"/generate/jobs/{job.job_id}")
    assert job_response.status_code == 500
    assert "Artifact URL signing is unavailable" in job_response.json()["detail"]
    assert "signing failed" in job_response.json()["detail"]

    report_response = client.get(f"/generate/reports/{report.report_id}")
    assert report_response.status_code == 500
    assert "Artifact URL signing is unavailable" in report_response.json()["detail"]
    assert "signing failed" in report_response.json()["detail"]


def test_report_endpoints_upgrade_sparse_citations_and_persist_the_upgrade(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)
    monkeypatch.setattr(generate, "materialize_browser_uri", lambda uri, *, base_url=None: uri)

    report = ReportDocument(
        report_id="report-router",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="impact-summary",
                type="text",
                title="Impact Summary",
                content="The witness says the defendant hit the stopped vehicle.",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                citations=[Citation(source_id="ev-1", provenance=ReportProvenance.evidence)],
            )
        ],
    )
    job = store.create_job(report=report)
    store.save_request(
        job.job_id,
        GenerateReportRequest(
            bundle=CaseEvidenceBundle(
                case_id="case-router",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-1",
                        kind=EvidenceItemType.transcript,
                        title="Witness Transcript",
                        summary="The witness says the defendant hit the stopped vehicle.",
                    )
                ],
            ),
            user_id="user-1",
        ),
    )

    client = TestClient(app)
    response = client.get(f"/generate/reports/{report.report_id}")

    assert response.status_code == 200
    assert response.json()["sections"][0]["citations"] == []

    persisted = store.get_report(report.report_id)
    assert persisted is not None
    assert persisted.sections[0].citations == []


def test_report_endpoints_dedupe_duplicate_sections_and_persist_the_upgrade(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)
    monkeypatch.setattr(generate, "materialize_browser_uri", lambda uri, *, base_url=None: uri)

    report = ReportDocument(
        report_id="report-router",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="image-impact",
                type="image",
                title="Impact Still",
                content=None,
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                media=[
                    MediaAsset(
                        kind=MediaAssetKind.image,
                        uri="gs://test-bucket/reports/report-router/media/impact.png",
                        generator="gemini-image",
                        manifest_uri="gs://test-bucket/reports/report-router/media/impact.manifest.json",
                        state=ReportBlockState.ready,
                    )
                ],
            ),
            ReportBlock(
                id="image-impact",
                type="image",
                title="Impact Still",
                content="Canonical prompt-bearing block",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                media=[
                    MediaAsset(
                        kind=MediaAssetKind.image,
                        uri="gs://test-bucket/reports/report-router/media/impact.png",
                        generator="gemini-image",
                        manifest_uri="gs://test-bucket/reports/report-router/media/impact.manifest.json",
                        state=ReportBlockState.ready,
                    )
                ],
            ),
        ],
    )
    job = store.create_job(report=report)

    client = TestClient(app)
    response = client.get(f"/generate/reports/{report.report_id}")

    assert response.status_code == 200
    body = response.json()
    assert [section["id"] for section in body["sections"]] == ["image-impact"]
    assert body["sections"][0]["content"] == "Canonical prompt-bearing block"

    persisted = store.get_report(report.report_id)
    assert persisted is not None
    assert len(persisted.sections) == 1
    assert persisted.sections[0].content == "Canonical prompt-bearing block"
