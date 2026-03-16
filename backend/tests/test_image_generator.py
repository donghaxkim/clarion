import asyncio
import json

from app.models import VisualSceneActor, VisualSceneSpec, VisualSceneStyle
from app.services.generation.image_generator import GeminiImageGenerator


def _upload_recorder():
    uploads = {}

    def _upload(data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
        uploads[gcs_key] = {"data": data, "content_type": content_type}
        return f"gs://test-bucket/{gcs_key}"

    return uploads, _upload


def test_image_generator_manifest_includes_prompt_metadata():
    uploads, upload_fn = _upload_recorder()
    generator = GeminiImageGenerator(upload_bytes_fn=upload_fn)
    generator._generate_sync = lambda *, prompt: (b"png-bytes", "gemini-3-pro-image-preview")

    scene_spec = VisualSceneSpec(
        scene_key="signal-state",
        visual_goal="show the signal state and vehicle placement before entry",
        style=VisualSceneStyle.top_down_diagram,
        camera_framing="top-down view of the intersection approaches",
        actors=[
            VisualSceneActor(
                actor_id="pickup",
                label="black pickup truck",
                kind="pickup truck",
                color="black",
                evidence_refs=["ev-1"],
            )
        ],
    )

    asyncio.run(
        generator.generate(
            case_id="case-123",
            report_id="report-123",
            block_id="signal-image",
            prompt="Create a detailed top-down diagram of the vehicles at the yellow light.",
            prompt_source="scene_spec_v1",
            camera_mode="top_down_diagram",
            visual_scene_spec=scene_spec,
        )
    )

    manifest_key = "reports/case-123/report-123/media/signal-image.manifest.json"
    manifest_payload = json.loads(uploads[manifest_key]["data"].decode("utf-8"))
    assert manifest_payload["prompt_source"] == "scene_spec_v1"
    assert manifest_payload["camera_mode"] == "top_down_diagram"
    assert manifest_payload["visual_scene_spec"]["scene_key"] == "signal-state"
