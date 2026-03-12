from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Citation,
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


class _NoopOrchestrator:
    async def run_job(self, job_id, payload):  # pragma: no cover - scheduled in background
        del job_id, payload
        return None


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
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "orchestrator", _NoopOrchestrator())

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


def test_stream_and_report_endpoints_return_job_events(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "orchestrator", _NoopOrchestrator())
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


def test_local_artifact_route_serves_local_files_when_enabled(monkeypatch, tmp_path):
    artifact = tmp_path / "reports/case-router/demo/video.mp4"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"video-bytes")

    monkeypatch.setattr(generate, "GCS_ALLOW_LOCAL_FALLBACK", True)
    monkeypatch.setattr(generate, "LOCAL_ARTIFACTS_DIR", str(tmp_path))

    client = TestClient(app)
    response = client.get("/generate/artifacts/reports/case-router/demo/video.mp4")
    assert response.status_code == 200
    assert response.content == b"video-bytes"
