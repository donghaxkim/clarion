from app.models import ReconstructionJobRequest

_NO_TEXT_GUIDANCE = (
    "Avoid any visible text, subtitles, captions, labels, signs, watermarks, "
    "interface elements, or document text in the rendered video."
)


def build_prompt(payload: ReconstructionJobRequest) -> str:
    evidence_block = ", ".join(payload.evidence_refs)
    reference_guidance = ""
    if payload.reference_image_uris:
        reference_guidance = (
            "Use reference images for scene consistency, but do not invent unsupported objects or actors."
        )

    return (
        "Create a factual incident reconstruction video suitable for legal report support. "
        "Keep the scene physically plausible and avoid cinematic exaggeration. "
        f"{_NO_TEXT_GUIDANCE} "
        f"Scene: {payload.scene_description}. "
        f"Evidence references: {evidence_block}. "
        f"Aspect ratio: {payload.aspect_ratio.value}. "
        f"Duration: {payload.duration_sec} seconds. "
        f"{reference_guidance}"
    ).strip()


def build_refined_prompt(payload: ReconstructionJobRequest) -> str:
    return (
        f"{build_prompt(payload)} "
        "Refine motion continuity, preserve relative object positions, and improve temporal smoothness."
    )


def build_fallback_prompt(payload: ReconstructionJobRequest) -> str:
    return (
        "Create a simple, neutral reconstruction clip with static camera motion and clear object trajectories. "
        f"{_NO_TEXT_GUIDANCE} "
        f"Scene: {payload.scene_description}. "
        "Do not add extra entities, weather changes, or dramatic effects."
    )
