from app.models import ReconstructionJobRequest
from app.services.video.reconstruction.prompt_builder import (
    build_fallback_prompt,
    build_prompt,
    build_refined_prompt,
)


def _payload() -> ReconstructionJobRequest:
    return ReconstructionJobRequest(
        case_id="case-123",
        section_id="section-1",
        scene_description="A witness view of the intersection just before impact.",
        evidence_refs=["ev-1"],
        duration_sec=4,
    )


def test_build_prompt_includes_no_text_guidance():
    prompt = build_prompt(_payload()).lower()

    assert "avoid any visible text" in prompt
    assert "subtitles" in prompt
    assert "watermarks" in prompt


def test_build_refined_prompt_preserves_no_text_guidance():
    prompt = build_refined_prompt(_payload()).lower()

    assert "avoid any visible text" in prompt


def test_build_fallback_prompt_includes_no_text_guidance():
    prompt = build_fallback_prompt(_payload()).lower()

    assert "avoid any visible text" in prompt


def test_build_prompt_uses_precomputed_prompt_when_available():
    payload = _payload().model_copy(
        update={
            "prompt": "Create an evidence-grounded motion reconstruction with a black pickup truck in the left-turn lane and an eastbound sedan braking before impact.",
        }
    )

    prompt = build_prompt(payload)

    assert "black pickup truck" in prompt.lower()
    assert "eastbound sedan" in prompt.lower()
