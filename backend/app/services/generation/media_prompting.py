from __future__ import annotations

from typing import Iterable

from app.agents.reporting.types import MediaRequest, TimelineEvent
from app.models import ReportBlockType, VisualSceneActor, VisualSceneSpec, VisualSceneStyle

PROMPT_SOURCE_SCENE_SPEC = "scene_spec_v1"

_IMAGE_NEGATIVE_PROMPTS = (
    "no visible text",
    "no captions",
    "no labels",
    "no lane arrows",
    "no road symbols",
    "no legend",
    "no interface overlays",
    "no watermark",
    "no extra vehicles",
    "no extra pedestrians",
    "no unsupported scene objects",
    "no dramatic effects",
)

_VIDEO_NEGATIVE_PROMPTS = (
    "no visible text",
    "no captions",
    "no labels",
    "no interface overlays",
    "no watermark",
    "no extra vehicles",
    "no extra pedestrians",
    "no unsupported objects",
    "no cinematic camera moves",
    "no explosions",
    "no smoke",
    "no fire",
    "no flashing police lights",
    "no weather changes",
    "no exaggerated damage",
)


def normalize_media_request_from_scene_spec(
    request: MediaRequest,
    event: TimelineEvent | None,
) -> tuple[MediaRequest | None, str | None]:
    spec = request.visual_scene_spec or (event.visual_scene_spec if event is not None else None)
    if spec is None:
        return request, None

    if not _has_sufficient_grounding(spec, request.block_type):
        return (
            None,
            f"{request.block_id} omitted: insufficient grounded visual detail for prompt generation",
        )

    if request.block_type == ReportBlockType.image:
        prompt = build_image_prompt(spec)
        return (
            request.model_copy(
                update={
                    "prompt": prompt,
                    "scene_description": build_scene_summary(spec),
                    "negative_prompt": None,
                    "prompt_source": PROMPT_SOURCE_SCENE_SPEC,
                    "camera_mode": spec.style.value,
                    "visual_scene_spec": spec,
                }
            ),
            None,
        )

    negative_prompt = build_reconstruction_negative_prompt(spec)
    return (
        request.model_copy(
            update={
                "prompt": build_reconstruction_prompt(spec),
                "scene_description": build_scene_summary(spec),
                "negative_prompt": negative_prompt,
                "prompt_source": PROMPT_SOURCE_SCENE_SPEC,
                "camera_mode": spec.style.value,
                "visual_scene_spec": spec,
            }
        ),
        None,
    )


def build_image_prompt(spec: VisualSceneSpec) -> str:
    parts = [
        _image_intro(spec),
        f"Visual goal: {spec.visual_goal}.",
    ]

    actor_text = _actor_clause(spec.actors)
    if actor_text:
        parts.append(f"Include these grounded subjects: {actor_text}.")

    traffic = _detail_clause(spec.traffic_control_details)
    if traffic:
        parts.append(f"Traffic-control details: {traffic}.")

    environment = _detail_clause(spec.environment_details)
    if environment:
        parts.append(f"Environment details: {environment}.")

    grounded = _detail_clause(spec.grounded_facts)
    if grounded:
        parts.append(f"Grounded spatial facts: {grounded}.")

    interpolated = _detail_clause(spec.interpolated_details)
    if interpolated:
        parts.append(
            f"Use only these neutral interpolations where evidence is silent: {interpolated}."
        )

    parts.append(
        "Keep the composition simple, evidence-grounded, and easy to read in a legal report."
    )
    parts.append(
        f"Avoid {_negative_clause([*_IMAGE_NEGATIVE_PROMPTS, *spec.negative_prompt_tags])}."
    )
    return " ".join(part for part in parts if part)


def build_reconstruction_prompt(spec: VisualSceneSpec) -> str:
    parts = [
        _reconstruction_intro(spec),
        f"Scene objective: {spec.visual_goal}.",
    ]

    actor_text = _actor_clause(spec.actors)
    if actor_text:
        parts.append(f"Use these grounded actors and vehicle placements: {actor_text}.")

    traffic = _detail_clause(spec.traffic_control_details)
    if traffic:
        parts.append(f"Traffic-control details: {traffic}.")

    environment = _detail_clause(spec.environment_details)
    if environment:
        parts.append(f"Environment details: {environment}.")

    grounded = _detail_clause(spec.grounded_facts)
    if grounded:
        parts.append(f"Grounded scene facts: {grounded}.")

    beats = _motion_clause(spec)
    if beats:
        parts.append(f"Motion beats in order: {beats}.")

    interpolated = _detail_clause(spec.interpolated_details)
    if interpolated:
        parts.append(
            f"Use only these neutral interpolations where evidence is silent: {interpolated}."
        )

    parts.append(
        "Keep timing, spacing, motion, and camera behavior physically plausible and neutral."
    )
    return " ".join(part for part in parts if part)


def build_reconstruction_negative_prompt(spec: VisualSceneSpec) -> str:
    return _negative_clause([*_VIDEO_NEGATIVE_PROMPTS, *spec.negative_prompt_tags])


def build_scene_summary(spec: VisualSceneSpec) -> str:
    summary_parts = [spec.visual_goal]
    actor_text = _actor_clause(spec.actors[:2])
    if actor_text:
        summary_parts.append(actor_text)
    grounded = _detail_clause(spec.grounded_facts[:2])
    if grounded:
        summary_parts.append(grounded)
    return " ".join(part for part in summary_parts if part).strip()


def _has_sufficient_grounding(spec: VisualSceneSpec, block_type: ReportBlockType) -> bool:
    # TODO: implement this properly for real evidence
    # has_scene_detail = bool(spec.actors or spec.traffic_control_details or spec.grounded_facts)
    # if block_type == ReportBlockType.image:
    #     return has_scene_detail
    # return bool(spec.motion_beats) and has_scene_detail
    return True


def _image_intro(spec: VisualSceneSpec) -> str:
    if spec.style == VisualSceneStyle.witness_view:
        return (
            f"Create a clean, text-free witness-view still for a legal report from this framing: {spec.camera_framing}."
        )
    if spec.style == VisualSceneStyle.grounded_motion:
        return (
            f"Create a clean, text-free still that freezes a grounded moment of motion using this framing: {spec.camera_framing}."
        )
    return (
        f"Create a clean, text-free top-down or diagrammatic still for a legal report using this framing: {spec.camera_framing}."
    )


def _reconstruction_intro(spec: VisualSceneSpec) -> str:
    if spec.style == VisualSceneStyle.witness_view:
        return (
            f"Create an evidence-grounded motion reconstruction from the described witness-eye framing: {spec.camera_framing}."
        )
    return (
        f"Create an evidence-grounded motion reconstruction for a legal report using this framing: {spec.camera_framing}."
    )


def _actor_clause(actors: Iterable[VisualSceneActor]) -> str:
    descriptions = [_describe_actor(actor) for actor in actors]
    return _join_items([description for description in descriptions if description])


def _describe_actor(actor: VisualSceneActor) -> str:
    parts = [actor.label]
    qualifiers: list[str] = []
    if actor.kind and actor.kind.casefold() not in actor.label.casefold():
        qualifiers.append(actor.kind)
    if actor.color and actor.color.casefold() not in actor.label.casefold():
        qualifiers.append(actor.color)
    if actor.travel_direction:
        qualifiers.append(f"traveling {actor.travel_direction}")
    if actor.lane_position:
        qualifiers.append(f"in {actor.lane_position}")
    if actor.relative_position:
        qualifiers.append(actor.relative_position)
    if actor.signal_state:
        qualifiers.append(f"with a {actor.signal_state} signal")
    if actor.action:
        qualifiers.append(actor.action)

    if qualifiers:
        parts.append(f"({'; '.join(qualifiers)})")
    return " ".join(part for part in parts if part)


def _motion_clause(spec: VisualSceneSpec) -> str:
    beats = [beat.description for beat in sorted(spec.motion_beats, key=lambda item: item.order)]
    return _join_items(beats)


def _detail_clause(details: Iterable[str]) -> str:
    return _join_items(details)


def _negative_clause(details: Iterable[str]) -> str:
    return _join_items(_unique_preserving_order(details))


def _join_items(items: Iterable[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered
