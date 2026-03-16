from app.main import app
from app.models import ReconstructionJobStatus, ReconstructionResult
from app.routers import reconstruction
from app.services.video.reconstruction.job_store import ReconstructionJobStore
from fastapi.testclient import TestClient


class _RecordingDispatcher:
    def __init__(self):
        self.job_ids: list[str] = []

    def dispatch_reconstruction_job(self, job_id: str) -> str:
        self.job_ids.append(job_id)
        return f"reconstruction-{job_id}"


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
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(reconstruction, "job_store", store)
    monkeypatch.setattr(reconstruction, "dispatcher", dispatcher)

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
    assert dispatcher.job_ids == [body["job_id"]]
    saved_request = store.load_request(body["job_id"])
    assert saved_request.case_id == "case_123"


def test_get_reconstruction_job_returns_404_for_unknown_job(monkeypatch):
    store = ReconstructionJobStore("ignored")
    monkeypatch.setattr(reconstruction, "job_store", store)
    client = TestClient(app)
    response = client.get("/reconstruction/jobs/does-not-exist")
    assert response.status_code == 404


def test_polling_endpoint_reflects_status_transitions(monkeypatch, tmp_path):
    store = ReconstructionJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(reconstruction, "job_store", store)
    monkeypatch.setattr(reconstruction, "dispatcher", dispatcher)
    monkeypatch.setattr(
        reconstruction,
        "materialize_browser_uri",
        lambda uri, *, base_url=None: (
            None if uri is None else uri.replace("gs://", "https://signed.test/")
        ),
    )

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

    store.update_status(
        job_id,
        status=ReconstructionJobStatus.completed,
        progress=100,
        result=ReconstructionResult(
            video_gcs_uri="gs://test-bucket/reconstructions/job/video.mp4",
            video_url="gs://test-bucket/reconstructions/job/video.mp4",
            model_used="veo-final",
            duration_sec=8,
            evidence_refs=["ev_1", "ev_2"],
            manifest_gcs_uri="gs://test-bucket/reconstructions/job/manifest.json",
        ),
    )
    completed_resp = client.get(f"/reconstruction/jobs/{job_id}")
    assert completed_resp.status_code == 200
    assert (
        completed_resp.json()["result"]["video_url"]
        == "https://signed.test/test-bucket/reconstructions/job/video.mp4"
    )


def test_polling_endpoint_returns_500_when_signing_fails(monkeypatch, tmp_path):
    store = ReconstructionJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(reconstruction, "job_store", store)
    monkeypatch.setattr(reconstruction, "dispatcher", dispatcher)

    def _raise_materialization_error(uri, *, base_url=None):
        del uri, base_url
        raise RuntimeError("signing failed")

    monkeypatch.setattr(
        reconstruction,
        "materialize_browser_uri",
        _raise_materialization_error,
    )

    client = TestClient(app)
    create_resp = client.post("/reconstruction/jobs", json=_payload())
    job_id = create_resp.json()["job_id"]

    store.update_status(
        job_id,
        status=ReconstructionJobStatus.completed,
        progress=100,
        result=ReconstructionResult(
            video_gcs_uri="gs://test-bucket/reconstructions/job/video.mp4",
            video_url="gs://test-bucket/reconstructions/job/video.mp4",
            model_used="veo-final",
            duration_sec=8,
            evidence_refs=["ev_1", "ev_2"],
            manifest_gcs_uri="gs://test-bucket/reconstructions/job/manifest.json",
        ),
    )

    completed_resp = client.get(f"/reconstruction/jobs/{job_id}")
    assert completed_resp.status_code == 500
    assert "Artifact URL signing is unavailable" in completed_resp.json()["detail"]
    assert "signing failed" in completed_resp.json()["detail"]
