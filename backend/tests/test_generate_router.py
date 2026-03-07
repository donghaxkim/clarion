from fastapi.testclient import TestClient

from app.main import app
from app.models import ReportDocument, ReportGenerationJobStatus, ReportStatus
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


def test_stream_and_report_endpoints_return_job_events(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "orchestrator", _NoopOrchestrator())

    report = ReportDocument(report_id="report-router", status=ReportStatus.running)
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
    store.mark_completed(job.job_id, report=completed_report, artifacts=None)

    client = TestClient(app)
    stream_response = client.get(f"/generate/jobs/{job.job_id}/stream")
    assert stream_response.status_code == 200
    assert "event: job.started" in stream_response.text
    assert "event: job.completed" in stream_response.text

    report_response = client.get(f"/generate/reports/{report.report_id}")
    assert report_response.status_code == 200
    assert report_response.json()["report_id"] == report.report_id
