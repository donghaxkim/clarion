import asyncio
import json

from app.config import VEO_FAST_MODEL, VEO_FINAL_MODEL
from app.models import (
    QualityMode,
    ReconstructionJobRequest,
    ReconstructionJobStatus,
    VisualSceneActor,
    VisualSceneSpec,
    VisualSceneStyle,
)
from app.services.video.reconstruction.job_store import ReconstructionJobStore
from app.services.video.reconstruction.orchestrator import ReconstructionOrchestrator


class _FakeVeoClient:
    def __init__(self, *, fail_first_n: int = 0, always_fail: bool = False):
        self.fail_first_n = fail_first_n
        self.always_fail = always_fail
        self.calls: list[dict] = []

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        duration_sec: int,
        aspect_ratio: str,
        reference_image_uris: list[str] | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "duration_sec": duration_sec,
                "aspect_ratio": aspect_ratio,
                "reference_image_uris": reference_image_uris or [],
                "negative_prompt": negative_prompt,
                "seed": seed,
            }
        )
        if self.always_fail:
            raise RuntimeError("generation failed")
        if self.fail_first_n > 0:
            self.fail_first_n -= 1
            raise RuntimeError("generation failed once")
        return b"fake-video-bytes"


def _payload(**overrides) -> ReconstructionJobRequest:
    data = {
        "case_id": "case_456",
        "section_id": "section_9",
        "scene_description": "Vehicle A rear-ends Vehicle B in stop-and-go traffic.",
        "prompt": "Create an evidence-grounded motion reconstruction with a black sedan braking into the rear of the pickup truck in stop-and-go traffic.",
        "prompt_source": "scene_spec_v1",
        "camera_mode": "grounded_motion",
        "evidence_refs": ["ev_10", "ev_11"],
        "reference_image_uris": ["gs://clarion-uploads/ref_a.jpg"],
        "visual_scene_spec": VisualSceneSpec(
            scene_key="rear-end",
            visual_goal="show approach, braking, and rear-end impact in stop-and-go traffic",
            style=VisualSceneStyle.grounded_motion,
            camera_framing="steady elevated roadside view",
            actors=[
                VisualSceneActor(
                    actor_id="sedan",
                    label="black sedan",
                    kind="sedan",
                    color="black",
                    evidence_refs=["ev_10"],
                )
            ],
        ),
        "duration_sec": 8,
        "aspect_ratio": "16:9",
        "negative_prompt": "no explosions",
        "seed": 42,
        "quality_mode": "fast_then_final",
    }
    data.update(overrides)
    return ReconstructionJobRequest(**data)


def _upload_recorder():
    uploads = {}

    def _upload(data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
        uploads[gcs_key] = {"data": data, "content_type": content_type}
        return f"gs://test-bucket/{gcs_key}"

    return uploads, _upload

def _run_job(
    tmp_path,
    *,
    payload: ReconstructionJobRequest | None = None,
    fake_client: _FakeVeoClient | None = None,
    upload_bytes_fn=None,
):
    store = ReconstructionJobStore(str(tmp_path / "jobs.json"))
    job = store.create_job()
    uploads, default_upload = _upload_recorder()

    orchestrator = ReconstructionOrchestrator(
        job_store=store,
        veo_client=fake_client or _FakeVeoClient(),
        upload_bytes_fn=upload_bytes_fn or default_upload,
    )
    payload = payload or _payload()
    asyncio.run(orchestrator.run_job(job.job_id, payload))
    return store, job, orchestrator.veo_client, uploads, payload


def test_fast_only_mode_performs_single_veo_call_and_writes_manifest(tmp_path):
    store, job, fake_client, uploads, payload = _run_job(
        tmp_path,
        payload=_payload(quality_mode=QualityMode.fast_only.value),
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["model"] == VEO_FAST_MODEL

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReconstructionJobStatus.completed
    assert final.result is not None
    assert final.result.model_used == VEO_FAST_MODEL
    assert final.result.evidence_refs == payload.evidence_refs
    assert final.result.video_url == final.result.video_gcs_uri

    manifest_key = f"reconstructions/{payload.case_id}/{job.job_id}/manifest.json"
    manifest_payload = json.loads(uploads[manifest_key]["data"].decode("utf-8"))
    assert manifest_payload["evidence_refs"] == payload.evidence_refs
    assert manifest_payload["prompt"] == payload.prompt
    assert manifest_payload["negative_prompt"] == payload.negative_prompt
    assert manifest_payload["prompt_source"] == payload.prompt_source
    assert manifest_payload["camera_mode"] == payload.camera_mode
    assert manifest_payload["visual_scene_spec"]["scene_key"] == "rear-end"


def test_fast_then_final_mode_performs_two_veo_calls(tmp_path):
    store, job, fake_client, _uploads, _payload_data = _run_job(
        tmp_path,
        payload=_payload(quality_mode=QualityMode.fast_then_final.value),
    )

    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["model"] == VEO_FAST_MODEL
    assert fake_client.calls[1]["model"] == VEO_FINAL_MODEL

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReconstructionJobStatus.completed
    assert final.result is not None
    assert final.result.model_used == VEO_FINAL_MODEL
    assert final.result.video_url == final.result.video_gcs_uri


def test_upload_failure_marks_job_failed(tmp_path):
    def _failing_upload(data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
        raise RuntimeError("upload failed")

    store, job, _fake_client, _uploads, _payload_data = _run_job(
        tmp_path,
        payload=_payload(quality_mode=QualityMode.fast_only.value),
        upload_bytes_fn=_failing_upload,
    )

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReconstructionJobStatus.failed
    assert final.error is not None
    assert "upload failed" in final.error


def test_retry_path_runs_after_first_generation_failure(tmp_path):
    store, job, fake_client, _uploads, _payload_data = _run_job(
        tmp_path,
        payload=_payload(quality_mode=QualityMode.fast_only.value),
        fake_client=_FakeVeoClient(fail_first_n=1),
    )

    assert len(fake_client.calls) == 2
    assert "simple, neutral reconstruction clip" in fake_client.calls[1]["prompt"]

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReconstructionJobStatus.completed


def test_generation_failure_includes_primary_and_fallback_errors(tmp_path):
    store, job, _fake_client, _uploads, _payload_data = _run_job(
        tmp_path,
        payload=_payload(quality_mode=QualityMode.fast_only.value),
        fake_client=_FakeVeoClient(always_fail=True),
    )

    final = store.get_job(job.job_id)
    assert final is not None
    assert final.status == ReconstructionJobStatus.failed
    assert final.error is not None
    assert "Veo generation failed after retry" in final.error
    assert "primary=RuntimeError: generation failed" in final.error
    assert "fallback=RuntimeError: generation failed" in final.error
