from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.models import (
    CaseEvidenceBundle,
    Citation,
    EntityMention,
    EventCandidate,
    EvidenceItem as ReportEvidenceItem,
    EvidenceItemType,
    SourceSpan,
)
from app.models.schema import CaseFile, Entity, EvidenceItem as LegacyEvidenceItem
from app.services.generation.report_citations import build_evidence_citation

_DOCUMENT_EVENT_HINTS = (
    "interview",
    "statement",
    "attestation",
    "signature",
    "signed",
    "document id",
    "case number",
    "taken by",
    "statement date",
    "statement time",
    "method:",
    "approximate duration",
    "investigator",
    "witness signature",
    "recorded phone interview",
    "recorded in-person interview",
    "legal intake center",
)

_NON_SCENE_HINTS = (
    "called 911",
    "police arrived",
    "contact information",
    "provided a written statement",
    "phone number",
    "email",
    "address:",
    "i pulled over",
    "went forward to check whether",
    "i got out",
)

_INCIDENT_TIMESTAMP_HINTS = (
    "incident occurs",
    "collision",
    "crash",
    "impact",
)


@dataclass(frozen=True)
class SceneCue:
    evidence_id: str
    text: str
    excerpt: str
    source_label: str
    segment_id: str | None = None
    page_number: int | None = None
    source_uri: str | None = None
    priority: int = 0
    citation_allowed: bool = True


@dataclass(frozen=True)
class SceneDefinition:
    key: str
    sort_key: str
    title: str
    matchers: tuple[str, ...]
    image_prompt_hint: str | None = None
    scene_direction: str | None = None
    public_context_queries: tuple[str, ...] = ()


_SCENE_DEFINITIONS: tuple[SceneDefinition, ...] = (
    SceneDefinition(
        key="signal_state",
        sort_key="0010",
        title="Traffic signal state before entry",
        matchers=(
            "yellow light",
            "green light",
            "red light",
            "signal changed to yellow",
            "traffic light",
            "light for",
            "entered on a yellow",
            "continued through the yellow",
        ),
        image_prompt_hint=(
            "Text-free, diagrammatic top-down view of the signalized intersection "
            "showing the traffic-light state and the relevant vehicles' positions "
            "immediately before entry."
        ),
        public_context_queries=("signalized intersection traffic-control context",),
    ),
    SceneDefinition(
        key="witness_viewpoint",
        sort_key="0020",
        title="Witness viewpoint and line of sight",
        matchers=(
            "clear view",
            "unobstructed view",
            "nothing was blocking my view",
            "line of sight",
            "direct line of sight",
            "observation point",
            "from where i sat",
            "about 25 feet from the marked crosswalk",
        ),
        image_prompt_hint=(
            "Text-free first-person witness-view still from the described observation "
            "point, showing the relevant lanes and what was visible toward the conflict area."
        ),
        public_context_queries=("line-of-sight and visibility context for a roadway witness viewpoint",),
    ),
    SceneDefinition(
        key="pre_impact_positioning",
        sort_key="0030",
        title="Pre-impact vehicle positioning",
        matchers=(
            "left-turn lane",
            "left-turn pocket",
            "turn pocket",
            "waiting in the left-turn",
            "sitting in the left-turn lane",
            "stopped",
            "crept forward",
            "approaching",
            "came up behind",
            "inside westbound lane",
            "eastbound sedan",
        ),
        image_prompt_hint=(
            "Text-free, diagrammatic top-down still showing the relevant vehicles' lane "
            "positions and static placement immediately before the turn and entry."
        ),
    ),
    SceneDefinition(
        key="collision_sequence",
        sort_key="0040",
        title="Collision sequence",
        matchers=(
            "turned left across",
            "started its left turn",
            "initiated the turn",
            "continued through the yellow",
            "did not have enough time",
            "hit its brakes",
            "heard tire noise",
            "braked late",
            "struck",
            "hit the pickup",
            "collision",
            "impact",
        ),
        scene_direction=(
            "Create an evidence-grounded motion reconstruction of the relevant vehicles "
            "approaching the intersection, the turning vehicle crossing the opposing lane, "
            "the braking response, the impact, and only the short post-impact motion needed "
            "to explain the mechanics. Keep timing, spacing, and movement neutral and "
            "physically plausible, with no text or cinematic embellishment."
        ),
    ),
    SceneDefinition(
        key="impact_location",
        sort_key="0050",
        title="Impact location in the intersection",
        matchers=(
            "near the center of the intersection",
            "middle of the intersection",
            "east of center",
            "passenger side area",
            "passenger-side front door area",
            "point of impact",
            "struck the passenger side",
        ),
        image_prompt_hint=(
            "Text-free, diagrammatic top-down still showing the point of impact in the "
            "intersection and each vehicle's orientation at contact."
        ),
    ),
    SceneDefinition(
        key="post_impact_positions",
        sort_key="0060",
        title="Post-impact resting positions",
        matchers=(
            "after the crash",
            "after impact",
            "rolled toward",
            "ended up",
            "came to rest",
            "ending farther east after contact",
            "final rest positions",
        ),
        image_prompt_hint=(
            "Text-free, diagrammatic top-down still showing the vehicles' final post-impact "
            "positions relative to the intersection."
        ),
    ),
)


def build_case_evidence_bundle(case: CaseFile, *, case_summary: str | None = None) -> CaseEvidenceBundle:
    report_evidence_items = [build_report_evidence_item(item) for item in case.evidence]
    return CaseEvidenceBundle(
        case_id=case.id,
        case_summary=case_summary or case.intake_summary or case.title,
        evidence_items=report_evidence_items,
        event_candidates=derive_scene_event_candidates(report_evidence_items),
        entities=[build_entity_mention(entity) for entity in case.entities],
    )


def build_report_evidence_item(item: LegacyEvidenceItem) -> ReportEvidenceItem:
    analysis = getattr(item, "_analysis", None) or {}
    return ReportEvidenceItem(
        evidence_id=item.id,
        kind=map_legacy_evidence_type(item.evidence_type),
        title=item.filename,
        summary=item.summary,
        extracted_text=item.content.text,
        media_uri=item.media.url,
        source_uri=item.media.url,
        source_spans=_build_source_spans(item, analysis),
        metadata=_build_evidence_metadata(item, analysis),
    )


def build_entity_mention(entity: Entity) -> EntityMention:
    parts: list[str] = []
    if entity.aliases:
        parts.append(f"Aliases: {', '.join(entity.aliases)}.")
    if entity.mentions:
        parts.append(f"Source mentions: {len(entity.mentions)}.")
    return EntityMention(
        entity_id=entity.id,
        name=entity.name,
        role=entity.type,
        description=" ".join(parts) or None,
    )


def derive_scene_event_candidates(evidence_items: list[ReportEvidenceItem]) -> list[EventCandidate]:
    timestamp_label = _incident_timestamp_label(evidence_items)
    candidates: list[EventCandidate] = []

    for definition in _SCENE_DEFINITIONS:
        cues = _collect_scene_cues(evidence_items, definition.matchers)
        if not cues:
            continue

        evidence_refs = _ordered_evidence_refs(cues)
        candidates.append(
            EventCandidate(
                event_id=definition.key,
                title=definition.title,
                description=_build_scene_description(definition, cues),
                sort_key=definition.sort_key,
                timestamp_label=timestamp_label,
                evidence_refs=evidence_refs,
                citations=_candidate_citations(cues),
                scene_description=(
                    _build_reconstruction_description(definition, cues)
                    if definition.scene_direction
                    else None
                ),
                image_prompt_hint=definition.image_prompt_hint,
                reference_image_uris=_reference_image_uris(evidence_items, evidence_refs),
                public_context_queries=list(definition.public_context_queries),
            )
        )

    return candidates


def map_legacy_evidence_type(evidence_type: Any) -> EvidenceItemType:
    value = getattr(evidence_type, "value", evidence_type)
    mapping = {
        "police_report": EvidenceItemType.official_record,
        "medical_record": EvidenceItemType.medical,
        "witness_statement": EvidenceItemType.transcript,
        "photo": EvidenceItemType.image,
        "dashcam_video": EvidenceItemType.video,
        "surveillance_video": EvidenceItemType.video,
        "insurance_document": EvidenceItemType.official_record,
        "diagram": EvidenceItemType.image,
        "other": EvidenceItemType.other,
    }
    return mapping.get(str(value), EvidenceItemType.other)


def _build_source_spans(item: LegacyEvidenceItem, analysis: dict[str, Any]) -> list[SourceSpan]:
    spans: list[SourceSpan] = []
    seen: set[tuple[Any, ...]] = set()

    for index, fact in enumerate(analysis.get("key_facts", []), start=1):
        span = _analysis_source_span(
            segment_id=f"{item.id}:fact:{index}",
            source_uri=item.media.url,
            payload=fact,
            fallback_snippet=fact.get("excerpt") or fact.get("fact"),
        )
        if span is None:
            continue
        key = (
            span.segment_id,
            span.page_number,
            tuple(span.time_range_ms or []),
            span.snippet,
            span.uri,
        )
        if key not in seen:
            seen.add(key)
            spans.append(span)

    return spans


def _analysis_source_span(
    *,
    segment_id: str,
    source_uri: str | None,
    payload: dict[str, Any],
    fallback_snippet: str | None,
) -> SourceSpan | None:
    page_number = _as_positive_int(payload.get("page"))
    time_range_ms: list[int] | None = None

    if payload.get("timestamp_start") is not None:
        start_ms = _seconds_to_ms(payload.get("timestamp_start"))
        end_ms = _seconds_to_ms(payload.get("timestamp_end", payload.get("timestamp_start")))
        if start_ms is not None and end_ms is not None:
            time_range_ms = [start_ms, max(start_ms, end_ms)]
    elif payload.get("mentioned_at") is not None:
        point_ms = _seconds_to_ms(payload.get("mentioned_at"))
        if point_ms is not None:
            time_range_ms = [point_ms, point_ms]

    snippet = _clean_text(fallback_snippet)
    if not page_number and not time_range_ms and not snippet:
        return None

    return SourceSpan(
        segment_id=segment_id,
        page_number=page_number,
        time_range_ms=time_range_ms,
        snippet=snippet,
        uri=source_uri,
    )


def _build_evidence_metadata(item: LegacyEvidenceItem, analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "legacy_evidence_type": getattr(item.evidence_type, "value", item.evidence_type),
        "labels": list(item.labels),
        "analysis_summary": analysis.get("summary") or item.summary,
        "entity_names": [entity.name for entity in item.entities],
        "key_facts": analysis.get("key_facts", []),
        "chronology_hints": analysis.get("timeline_events", []),
    }


def _incident_timestamp_label(evidence_items: list[ReportEvidenceItem]) -> str | None:
    for item in evidence_items:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        for event in metadata.get("chronology_hints", []):
            description = _clean_text(event.get("description"))
            if not description:
                continue
            lowered = description.lower()
            if _contains_any(lowered, _DOCUMENT_EVENT_HINTS):
                continue
            if _contains_any(lowered, _INCIDENT_TIMESTAMP_HINTS):
                return _clean_text(event.get("timestamp"))
    return None


def _collect_scene_cues(
    evidence_items: list[ReportEvidenceItem],
    matchers: tuple[str, ...],
) -> list[SceneCue]:
    cues: list[SceneCue] = []

    for item in evidence_items:
        for cue in _key_fact_cues(item, matchers):
            if not _contains_similar_cue(cues, cue):
                cues.append(cue)
        for cue in _text_fragment_cues(item, matchers):
            if not _contains_similar_cue(cues, cue):
                cues.append(cue)

    return cues


def _key_fact_cues(item: ReportEvidenceItem, matchers: tuple[str, ...]) -> list[SceneCue]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    cues: list[SceneCue] = []
    for index, fact in enumerate(metadata.get("key_facts", []), start=1):
        fact_text = _clean_text(fact.get("fact"))
        excerpt = _clean_text(fact.get("excerpt"))
        combined = " ".join(part for part in (fact_text, excerpt) if part).strip()
        lowered = combined.lower()
        if not lowered:
            continue
        if _contains_any(lowered, _DOCUMENT_EVENT_HINTS) or _contains_any(lowered, _NON_SCENE_HINTS):
            continue
        if _contains_any(lowered, matchers):
            span = _find_source_span(item, f"{item.evidence_id}:fact:{index}")
            cues.append(
                SceneCue(
                    evidence_id=item.evidence_id,
                    text=fact_text or excerpt or combined,
                    excerpt=excerpt or fact_text or combined,
                    source_label=_evidence_source_label(item),
                    segment_id=span.segment_id if span is not None else None,
                    page_number=_as_positive_int(fact.get("page")),
                    source_uri=item.source_uri or item.media_uri,
                    priority=0,
                    citation_allowed=True,
                )
            )
    return cues


def _text_fragment_cues(item: ReportEvidenceItem, matchers: tuple[str, ...]) -> list[SceneCue]:
    text = item.extracted_text or ""
    if not text:
        return []

    cues: list[SceneCue] = []
    page_number = 1
    for fragment in _text_fragments(text):
        lowered = fragment.lower()
        if "[page " in lowered:
            extracted_page = _page_number_from_fragment(lowered)
            if extracted_page is not None:
                page_number = extracted_page
            continue
        if _contains_any(lowered, _DOCUMENT_EVENT_HINTS) or _contains_any(lowered, _NON_SCENE_HINTS):
            continue
        if _contains_any(lowered, matchers) and _is_useful_scene_fragment(fragment):
            summary_text, citation_allowed = _rewrite_fragment_for_summary(fragment)
            if summary_text is None:
                continue
            span = (
                _ensure_fragment_source_span(item, fragment=fragment, page_number=page_number)
                if citation_allowed
                else None
            )
            cues.append(
                SceneCue(
                    evidence_id=item.evidence_id,
                    text=summary_text,
                    excerpt=fragment,
                    source_label=_evidence_source_label(item),
                    segment_id=(span.segment_id if span is not None else None),
                    page_number=page_number,
                    source_uri=item.source_uri or item.media_uri,
                    priority=1,
                    citation_allowed=citation_allowed,
                )
            )
    return cues


def _text_fragments(text: str) -> list[str]:
    flattened = text.replace("\r", "\n")
    raw_fragments = re.split(r"(?<=[.!?])\s+|\n+", flattened)
    cleaned: list[str] = []
    for fragment in raw_fragments:
        value = _clean_text(fragment)
        if not value or len(value) < 18:
            continue
        cleaned.append(value)
    return cleaned


def _page_number_from_fragment(fragment: str) -> int | None:
    match = re.search(r"\[page\s+(\d+)\]", fragment)
    if not match:
        return None
    return _as_positive_int(match.group(1))


def _ordered_evidence_refs(cues: list[SceneCue]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for cue in cues:
        if cue.evidence_id not in seen:
            seen.add(cue.evidence_id)
            refs.append(cue.evidence_id)
    return refs


def _build_scene_description(definition: SceneDefinition, cues: list[SceneCue]) -> str:
    fragments = _top_cue_texts(cues)
    summaries = {
        "signal_state": "Witness accounts ground the traffic-signal state and vehicle entry timing.",
        "witness_viewpoint": "Evidence grounds the witness observation point and line of sight toward the conflict area.",
        "pre_impact_positioning": "Evidence grounds the relevant vehicles' lane placement and positioning before impact.",
        "collision_sequence": "Evidence grounds the movement sequence leading into the collision.",
        "impact_location": "Evidence grounds where contact occurred within the intersection.",
        "post_impact_positions": "Evidence grounds the vehicles' post-impact rest positions.",
    }
    prefix = summaries.get(definition.key, "Evidence grounds this scene.")
    return _join_summary(prefix, fragments)


def _build_reconstruction_description(definition: SceneDefinition, cues: list[SceneCue]) -> str:
    detail = " ".join(_top_cue_texts(cues))
    if detail:
        return f"{definition.scene_direction} Grounding cues: {detail}"
    return definition.scene_direction or ""


def _top_cue_texts(cues: list[SceneCue], *, limit: int = 3) -> list[str]:
    preferred = _preferred_summary_cues(cues)
    fragments: list[str] = []
    seen: set[str] = set()
    for cue in preferred:
        normalized = _normalize_scene_text(cue.text)
        if normalized in seen:
            continue
        seen.add(normalized)
        fragments.append(_ensure_period(cue.text))
        if len(fragments) >= limit:
            break
    return fragments


def _reference_image_uris(
    evidence_items: list[ReportEvidenceItem],
    evidence_refs: list[str],
) -> list[str]:
    lookup = {item.evidence_id: item for item in evidence_items}
    uris: list[str] = []
    for evidence_id in evidence_refs:
        item = lookup.get(evidence_id)
        if item is None:
            continue
        if item.kind == EvidenceItemType.image and (item.media_uri or item.source_uri):
            uris.append(item.media_uri or item.source_uri or "")
        if len(uris) >= 3:
            break
    return uris


def _join_summary(prefix: str, fragments: list[str]) -> str:
    if not fragments:
        return prefix
    return f"{prefix} {' '.join(fragments)}".strip()


def _candidate_citations(cues: list[SceneCue], *, limit: int = 3) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str | None, int | None, str]] = set()
    for cue in _preferred_summary_cues(cues):
        if not cue.citation_allowed or cue.segment_id is None:
            continue
        key = (cue.evidence_id, cue.segment_id, cue.page_number, cue.excerpt.lower())
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            build_evidence_citation(
                cue.evidence_id,
                source_label=cue.source_label,
                excerpt=cue.excerpt,
                segment_id=cue.segment_id,
                page_number=cue.page_number,
                uri=cue.source_uri,
            )
        )
        if len(citations) >= limit:
            break
    return citations


def _preferred_summary_cues(cues: list[SceneCue]) -> list[SceneCue]:
    fact_cues = [cue for cue in cues if cue.priority == 0]
    return fact_cues or cues


def _contains_similar_cue(existing: list[SceneCue], candidate: SceneCue) -> bool:
    for cue in existing:
        if cue.evidence_id != candidate.evidence_id:
            continue
        if cue.segment_id and candidate.segment_id and cue.segment_id == candidate.segment_id:
            return True
        if _scene_texts_similar(cue.text, candidate.text):
            return True
    return False


def _scene_texts_similar(left: str, right: str) -> bool:
    normalized_left = _normalize_scene_text(left)
    normalized_right = _normalize_scene_text(right)
    if normalized_left == normalized_right:
        return True
    shorter, longer = sorted((normalized_left, normalized_right), key=len)
    return bool(shorter) and shorter in longer and len(shorter) >= max(24, int(len(longer) * 0.65))


def _normalize_scene_text(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(lowered.split())


def _find_source_span(item: ReportEvidenceItem, segment_id: str) -> SourceSpan | None:
    for span in item.source_spans:
        if span.segment_id == segment_id:
            return span
    return None


def _ensure_fragment_source_span(
    item: ReportEvidenceItem,
    *,
    fragment: str,
    page_number: int | None,
) -> SourceSpan:
    cleaned_fragment = _clean_text(fragment) or fragment.strip()
    for span in item.source_spans:
        if (
            span.page_number == page_number
            and _clean_text(span.snippet) == cleaned_fragment
        ):
            return span

    digest = hashlib.sha1(
        f"{page_number or 0}:{cleaned_fragment.lower()}".encode("utf-8")
    ).hexdigest()[:12]
    span = SourceSpan(
        segment_id=f"{item.evidence_id}:scene:{digest}",
        page_number=page_number,
        snippet=cleaned_fragment,
        uri=item.source_uri or item.media_uri,
    )
    item.source_spans.append(span)
    return span


def _evidence_source_label(item: ReportEvidenceItem) -> str:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    return (
        _clean_text(item.title)
        or _clean_text(metadata.get("filename"))
        or item.evidence_id
    )


def _is_useful_scene_fragment(fragment: str) -> bool:
    cleaned = _clean_text(fragment)
    if cleaned is None or len(cleaned) < 28:
        return False
    if cleaned[0].islower():
        return False
    return True


def _rewrite_fragment_for_summary(fragment: str) -> tuple[str | None, bool]:
    cleaned = _clean_text(fragment)
    if cleaned is None:
        return None, False

    lowered = cleaned.lower()
    if lowered.startswith(("after impact, i ", "after the crash, i ", "i pulled over")):
        return None, False

    if lowered.endswith("ended up") and " and " in cleaned:
        prefix = cleaned.rsplit(" and ", 1)[0]
        return (_clean_text(prefix), False)

    if lowered.endswith((" whether", " where", " when", " that", " which")):
        prefix = cleaned.rsplit(",", 1)[0] if "," in cleaned else None
        return (_clean_text(prefix), False)

    return cleaned, True


def _ensure_period(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _seconds_to_ms(value: Any) -> int | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return int(seconds * 1000)


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)
