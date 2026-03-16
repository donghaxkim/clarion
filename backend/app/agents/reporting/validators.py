from __future__ import annotations

import re
from collections.abc import Callable

from app.agents.reporting.types import ComposerOutput, MediaPlan, MediaRequest, TimelineEvent, TimelinePlan
from app.models import CaseEvidenceBundle, ReportBlockType, ReportProvenance, VisualSceneStyle
from app.services.generation.media_prompting import normalize_media_request_from_scene_spec

_MEDIA_DOCUMENT_HINTS = (
    "document",
    "report on paper",
    "piece of paper",
    "paperwork",
    "record page",
    "medical record",
    "police report",
    "witness statement",
    "transcript",
    "form",
    "page",
    "scan",
    "screenshot",
    "phone screen",
    "text message",
    "message thread",
)

_MEDIA_FILLER_HINTS = (
    "portrait",
    "headshot",
    "scales of justice",
    "gavel",
    "courthouse exterior",
    "hospital exterior",
    "ambulance lights",
    "police lights",
    "establishing shot",
    "generic room",
)

_IMAGE_MOTION_HINTS = (
    "collision",
    "crash",
    "impact",
    "sequence",
    "movement",
    "moving",
    "approach",
    "approaching",
    "driving",
    "walking",
    "running",
    "entering",
    "entered",
    "handoff",
    "throwing",
    "threw",
)

_IMAGE_STATIC_HINTS = (
    "traffic light",
    "signal state",
    "pedestrian signal",
    "crosswalk",
    "line of sight",
    "sightline",
    "obstruction",
    "visibility",
    "viewpoint",
    "witness view",
    "first-person",
    "top-down",
    "overhead",
    "diagram",
    "layout",
    "hazard",
    "position",
    "positioning",
    "standing",
    "body position",
    "placement",
    "placed",
    "door",
    "counter",
    "stairwell",
    "stairs",
)

_IMAGE_BAN_HINTS = _MEDIA_DOCUMENT_HINTS + _MEDIA_FILLER_HINTS + (
    "damage recreation",
    "vehicle damage",
    "property damage",
    "blurry cleanup",
    "weather-only",
    "injury illustration",
    "floor plan",
    "map",
    "blueprint",
)

_RECONSTRUCTION_BAN_HINTS = _MEDIA_DOCUMENT_HINTS + _MEDIA_FILLER_HINTS
_EVENT_BLOCK_ID_RE = re.compile(r"^event-[A-Za-z0-9_.:-]+$")
_CONTEXT_BLOCK_ID_RE = re.compile(r"^context-\d+$")


def validate_timeline_plan(bundle: CaseEvidenceBundle, plan: TimelinePlan) -> list[str]:
    issues: list[str] = []
    known_evidence = {item.evidence_id for item in bundle.evidence_items}
    previous_key = ""

    if not plan.timeline_events:
        issues.append("timeline plan must include at least one event")
        return issues

    for event in plan.timeline_events:
        if previous_key and event.sort_key < previous_key:
            issues.append("timeline events must be sorted by sort_key")
        previous_key = event.sort_key

        if not event.evidence_refs:
            issues.append(f"{event.event_id} is missing evidence_refs")
        missing_refs = [ref for ref in event.evidence_refs if ref not in known_evidence]
        if missing_refs:
            issues.append(f"{event.event_id} references unknown evidence ids: {missing_refs}")
        for citation in event.citations:
            if citation.source_id not in event.evidence_refs:
                issues.append(
                    f"{event.event_id} uses citation {citation.source_id} outside its evidence_refs"
                )
            if citation.provenance != ReportProvenance.evidence:
                issues.append(
                    f"{event.event_id} mixes evidence chronology with {citation.provenance.value} citations"
                )
            if not _citation_is_grounded(citation):
                issues.append(f"{event.event_id} has an unresolved evidence citation for {citation.source_id}")

    return issues


def validate_composer_output(output: ComposerOutput) -> list[str]:
    issues: list[str] = []
    previous_key = ""

    if not output.blocks:
        issues.append("composer output must include at least one block")
        return issues

    for block in output.blocks:
        if previous_key and block.sort_key < previous_key:
            issues.append("report blocks must be sorted by sort_key")
        previous_key = block.sort_key
        if block.type != ReportBlockType.text:
            issues.append(f"{block.id} must be a text block in composer output")
        if not _is_canonical_composer_block(block.id, provenance=block.provenance):
            issues.append(
                f"{block.id} is not a valid composer block id for {block.provenance.value}"
            )

        for citation in block.citations:
            if citation.provenance != block.provenance:
                issues.append(
                    f"{block.id} mixes {block.provenance.value} content with "
                    f"{citation.provenance.value} citations"
                )
            if block.provenance == ReportProvenance.evidence and not _citation_is_grounded(citation):
                issues.append(f"{block.id} has an unresolved evidence citation for {citation.source_id}")

    return issues


def normalize_composer_output(output: ComposerOutput, timeline: TimelinePlan) -> ComposerOutput:
    output = sanitize_composer_output(output)
    event_citation_lookup = {
        event.event_id: list(event.citations) for event in timeline.timeline_events if event.citations
    }

    updated_blocks = []
    changed = False
    sorted_blocks = sorted(output.blocks, key=lambda block: block.sort_key)
    if sorted_blocks != output.blocks:
        changed = True

    for block in sorted_blocks:
        if block.provenance != ReportProvenance.evidence or block.citations:
            updated_blocks.append(block)
            continue

        citations = []
        if block.id.startswith("event-"):
            event_id = block.id.removeprefix("event-")
            citations = event_citation_lookup.get(event_id, [])

        if citations:
            changed = True
            updated_blocks.append(block.model_copy(update={"citations": citations}))
            continue

        updated_blocks.append(block)

    if not changed:
        return output
    return output.model_copy(update={"blocks": updated_blocks})


def sanitize_composer_output(output: ComposerOutput) -> ComposerOutput:
    deduped_blocks = []
    seen_ids: set[str] = set()

    for block in reversed(output.blocks):
        if block.type != ReportBlockType.text:
            continue
        if not _is_canonical_composer_block(block.id, provenance=block.provenance):
            continue
        if block.id in seen_ids:
            continue
        seen_ids.add(block.id)
        deduped_blocks.append(block)

    deduped_blocks.reverse()
    if deduped_blocks == output.blocks:
        return output
    return output.model_copy(update={"blocks": deduped_blocks})


def normalize_media_plan(
    plan: MediaPlan,
    timeline: TimelinePlan,
    *,
    warnings: list[str] | None = None,
) -> MediaPlan:
    event_lookup = {
        f"event-{event.event_id}": event for event in timeline.timeline_events
    }
    image_requests = _normalize_media_requests(
        plan.image_requests,
        event_lookup=event_lookup,
        keep_request=_should_keep_image_request,
        warnings=warnings,
    )
    reconstruction_requests = _normalize_media_requests(
        plan.reconstruction_requests,
        event_lookup=event_lookup,
        keep_request=_should_keep_reconstruction_request,
        warnings=warnings,
    )

    if (
        image_requests == plan.image_requests
        and reconstruction_requests == plan.reconstruction_requests
    ):
        return plan

    return plan.model_copy(
        update={
            "image_requests": image_requests,
            "reconstruction_requests": reconstruction_requests,
        }
    )


def _normalize_media_requests(
    requests: list[MediaRequest],
    *,
    event_lookup: dict[str, TimelineEvent],
    keep_request: Callable[[MediaRequest, TimelineEvent | None], bool],
    warnings: list[str] | None = None,
) -> list[MediaRequest]:
    normalized: list[MediaRequest] = []
    seen_block_ids: set[str] = set()

    for request in requests:
        if request.block_id in seen_block_ids:
            continue
        seen_block_ids.add(request.block_id)
        event = event_lookup.get(request.anchor_block_id)
        request = _merge_request_visual_scene_spec(request, event)
        request, warning = normalize_media_request_from_scene_spec(request, event)
        if warning is not None and warnings is not None:
            warnings.append(warning)
        if request is None:
            continue
        if keep_request(request, event):
            normalized.append(request)

    return normalized


def _merge_request_visual_scene_spec(
    request: MediaRequest,
    event: TimelineEvent | None,
) -> MediaRequest:
    if request.visual_scene_spec is not None or event is None or event.visual_scene_spec is None:
        return request
    return request.model_copy(update={"visual_scene_spec": event.visual_scene_spec})


def _should_keep_image_request(
    request: MediaRequest,
    event: TimelineEvent | None,
) -> bool:
    if not request.prompt or not request.citations:
        return False
    if request.visual_scene_spec is not None and request.visual_scene_spec.style == VisualSceneStyle.grounded_motion:
        return False

    text = _media_request_text(request, event)
    if _contains_any(text, _IMAGE_BAN_HINTS):
        return False

    has_motion_hint = _contains_any(text, _IMAGE_MOTION_HINTS)
    has_static_hint = _contains_any(text, _IMAGE_STATIC_HINTS)
    if has_motion_hint and not has_static_hint:
        return False

    return True


def _should_keep_reconstruction_request(
    request: MediaRequest,
    event: TimelineEvent | None,
) -> bool:
    if not request.scene_description or not request.citations:
        return False

    text = _media_request_text(request, event)
    return not _contains_any(text, _RECONSTRUCTION_BAN_HINTS)


def _media_request_text(request: MediaRequest, event: TimelineEvent | None) -> str:
    parts = [
        request.title,
        request.prompt,
        request.scene_description,
    ]
    if event is not None:
        parts.extend(
            [
                event.title,
                event.narrative,
                event.scene_description,
                event.image_prompt,
            ]
        )
    return " ".join(part for part in parts if part).lower()


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _is_canonical_composer_block(block_id: str, *, provenance: ReportProvenance) -> bool:
    if provenance == ReportProvenance.public_context:
        return bool(_CONTEXT_BLOCK_ID_RE.match(block_id))
    return bool(_EVENT_BLOCK_ID_RE.match(block_id))


def _citation_is_grounded(citation) -> bool:
    if citation.provenance != ReportProvenance.evidence:
        return True
    return bool(
        citation.segment_id
        or citation.page_number
        or citation.time_range_ms
        or citation.excerpt
        or citation.snippet
    )
