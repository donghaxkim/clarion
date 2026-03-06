from app.main import app
from app.models import ReconstructionJobStatus
from app.routers import reconstruction
from app.services.video.reconstruction.job_store import ReconstructionJobStore
from fastapi.testclient import TestClient


class _NoopOrchestrator:
    async def run_job(self, job_id, payload):  # pragma: no cover - invoked by background task scheduling
        return None


def _discard_task(coro):
    coro.close()

    class _Task:
        done = True

    return _Task()


def _payload():
    return {
        "case_id": "case_123",
        "section_id": "section_abc",
        "scene_description": "Vehicle A and Vehicle B collide at an intersection.",
        "evidence_refs": ["ev_1", "ev_2"],
        "reference_image_uris": ["gs://clarion-uploads/ref1.jpg"],
        "duration_sec": 8,
        "aspect_ratio": "16:9",
        "negative_prompt": "no dramatic explosion",
        "seed": 101,
        "quality_mode": "fast_then_final",
    }


def test_create_reconstruction_job_returns_202_and_queued(monkeypatch, tmp_path):
    store = ReconstructionJobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(reconstruction, "job_store", store)
    monkeypatch.setattr(reconstruction, "orchestrator", _NoopOrchestrator())
    monkeypatch.setattr(reconstruction.asyncio, "create_task", _discard_task)

    client = TestClient(app)
    response = client.post("/reconstruction/jobs", json=_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["status"] == ReconstructionJobStatus.queued.value
    assert body["poll_url"] == f"/reconstruction/jobs/{body['job_id']}"

    stored = store.get_job(body["job_id"])
    assert stored is not None
    assert stored.status == ReconstructionJobStatus.queued
    assert stored.progress == 0


def test_get_reconstruction_job_returns_404_for_unknown_job():
    client = TestClient(app)
    response = client.get("/reconstruction/jobs/does-not-exist")
    assert response.status_code == 404


def test_polling_endpoint_reflects_status_transitions(monkeypatch, tmp_path):
    store = ReconstructionJobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(reconstruction, "job_store", store)
    monkeypatch.setattr(reconstruction, "orchestrator", _NoopOrchestrator())
    monkeypatch.setattr(reconstruction.asyncio, "create_task", _discard_task)

    client = TestClient(app)
    create_resp = client.post("/reconstruction/jobs", json=_payload())
    job_id = create_resp.json()["job_id"]

    store.update_status(job_id, status=ReconstructionJobStatus.running_fast, progress=35)
    running_resp = client.get(f"/reconstruction/jobs/{job_id}")
    assert running_resp.status_code == 200
    assert running_resp.json()["status"] == ReconstructionJobStatus.running_fast.value
    assert running_resp.json()["progress"] == 35

    store.update_status(job_id, status=ReconstructionJobStatus.uploading, progress=85)
    upload_resp = client.get(f"/reconstruction/jobs/{job_id}")
    assert upload_resp.status_code == 200
    assert upload_resp.json()["status"] == ReconstructionJobStatus.uploading.value
    assert upload_resp.json()["progress"] == 85
