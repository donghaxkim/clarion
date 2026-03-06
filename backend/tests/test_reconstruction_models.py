import pytest
from pydantic import ValidationError

from app.models import AspectRatio, QualityMode, ReconstructionJobRequest


def _base_payload(**overrides):
    payload = {
        "case_id": "case_123",
        "section_id": "section_1",
        "scene_description": "Vehicle A enters intersection and collides with Vehicle B.",
        "evidence_refs": ["ev_1"],
        "reference_image_uris": ["gs://clarion-uploads/ref1.jpg"],
        "duration_sec": 8,
        "aspect_ratio": "16:9",
        "negative_prompt": "no fire or explosions",
        "seed": 7,
        "quality_mode": "fast_then_final",
    }
    payload.update(overrides)
    return payload


def test_reconstruction_request_defaults():
    req = ReconstructionJobRequest(
        **_base_payload(
            reference_image_uris=[],
            duration_sec=8,
            quality_mode="fast_only",
            section_id=None,
            seed=None,
            negative_prompt=None,
        )
    )
    assert req.aspect_ratio == AspectRatio.landscape
    assert req.quality_mode == QualityMode.fast_only
    assert req.duration_sec == 8


@pytest.mark.parametrize("duration_sec", [4, 6, 8])
def test_reconstruction_request_accepts_supported_durations(duration_sec):
    req = ReconstructionJobRequest(**_base_payload(duration_sec=duration_sec))
    assert req.duration_sec == duration_sec


@pytest.mark.parametrize("duration_sec", [3, 5, 7, 9])
def test_reconstruction_request_rejects_unsupported_durations(duration_sec):
    with pytest.raises(ValidationError):
        ReconstructionJobRequest(**_base_payload(duration_sec=duration_sec))


def test_reconstruction_request_rejects_empty_evidence_refs():
    with pytest.raises(ValidationError):
        ReconstructionJobRequest(**_base_payload(evidence_refs=[]))


def test_reconstruction_request_rejects_more_than_3_reference_images():
    with pytest.raises(ValidationError):
        ReconstructionJobRequest(
            **_base_payload(
                reference_image_uris=[
                    "gs://clarion-uploads/ref1.jpg",
                    "gs://clarion-uploads/ref2.jpg",
                    "gs://clarion-uploads/ref3.jpg",
                    "gs://clarion-uploads/ref4.jpg",
                ]
            )
        )
