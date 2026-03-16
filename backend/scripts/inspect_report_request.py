#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import (  # noqa: E402
    CaseEvidenceBundle,
    EntityMention,
    EventCandidate,
    GenerateReportRequest,
    SourceSpan,
)
from app.models.schema import EvidenceItem as LegacyEvidenceItem  # noqa: E402
from app.services.case_service import (  # noqa: E402
    CaseWorkspaceRecord,
    CaseWorkspaceService,
    InMemoryCaseWorkspaceBackend,
    _map_legacy_evidence_type,
    case_workspace_service,
)
from app.services.parser.labeler import parse_evidence  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the current case-driven report-generation request payload and "
            "a richer preview built from parser analysis."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--case-id", help="Existing case ID to inspect from the configured backend.")
    source.add_argument(
        "--pdf",
        action="append",
        default=[],
        help="Local PDF/image/audio file to parse into a temporary in-memory case. Repeat for multiple files.",
    )
    parser.add_argument(
        "--case-title",
        default="Local inspection case",
        help="Case title for --pdf mode.",
    )
    parser.add_argument(
        "--case-summary",
        default=None,
        help="Case summary/description for --pdf mode. Defaults to the case title.",
    )
    parser.add_argument(
        "--user-id",
        default="clarion-user",
        help="User ID used when building the request payload.",
    )
    parser.add_argument(
        "--enable-public-context",
        choices=("true", "false", "null"),
        default="null",
        help="Explicit enable_public_context value for both payloads.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Explicit max_images value for both payloads.",
    )
    parser.add_argument(
        "--max-reconstructions",
        type=int,
        default=None,
        help="Explicit max_reconstructions value for both payloads.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enable_public_context = _parse_optional_bool(args.enable_public_context)

    try:
        if args.case_id:
            service = case_workspace_service
            record = service.require_case_record(args.case_id)
            source_mode = "existing_case"
            notes = [
                "current_request is the exact payload produced by CaseWorkspaceService.build_generate_request() for this case.",
                "enriched_request_preview is heuristic and inspection-only; it shows the kinds of parser-derived detail the live bridge is currently dropping.",
            ]
        else:
            service, record = _build_temp_case_from_files(
                file_paths=[Path(value) for value in args.pdf],
                case_title=args.case_title,
                case_summary=args.case_summary,
            )
            source_mode = "local_files"
            notes = [
                "current_request matches the current case-driven mapping shape, but media_uri/source_uri use local file URIs because this mode does not upload to storage.",
                "enriched_request_preview is heuristic and inspection-only; it shows the kinds of parser-derived detail the live bridge is currently dropping.",
            ]

        current_request = service.build_generate_request(
            record.case.id,
            user_id=args.user_id,
            enable_public_context=enable_public_context,
            max_images=args.max_images,
            max_reconstructions=args.max_reconstructions,
        )
        enriched_request = _build_enriched_request(
            record=record,
            user_id=args.user_id,
            enable_public_context=enable_public_context,
            max_images=args.max_images,
            max_reconstructions=args.max_reconstructions,
        )

        payload = {
            "source_mode": source_mode,
            "case_id": record.case.id,
            "notes": notes,
            "comparison_summary": _build_comparison_summary(current_request, enriched_request, record),
            "parser_analysis_summary": _build_parser_analysis_summary(record),
            "current_request": current_request.model_dump(mode="json"),
            "enriched_request_preview": enriched_request.model_dump(mode="json"),
            "derived_event_candidates_summary": _build_derived_event_summary(enriched_request),
        }
    except Exception as exc:
        print(f"inspect_report_request failed: {exc}", file=sys.stderr)
        return 1

    json.dump(payload, sys.stdout, indent=2 if args.pretty else None)
    if args.pretty:
        sys.stdout.write("\n")
    return 0


def _build_temp_case_from_files(
    *,
    file_paths: list[Path],
    case_title: str,
    case_summary: str | None,
) -> tuple[CaseWorkspaceService, CaseWorkspaceRecord]:
    if not file_paths:
        raise ValueError("At least one --pdf path is required in local file mode")

    backend = InMemoryCaseWorkspaceBackend()
    service = CaseWorkspaceService(backend=backend)
    record = service.create_case(
        title=case_title,
        description=case_summary or case_title,
    )
    for file_path in file_paths:
        resolved = file_path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        media_url = resolved.as_uri()
        evidence = parse_evidence(
            str(resolved),
            resolved.name,
            media_url,
        )
        if evidence is None:
            raise ValueError(f"Could not parse file: {resolved}")
        service.attach_evidence(record.case.id, evidence)
    return service, service.require_case_record(record.case.id)


def _build_enriched_request(
    *,
    record: CaseWorkspaceRecord,
    user_id: str,
    enable_public_context: bool | None,
    max_images: int | None,
    max_reconstructions: int | None,
) -> GenerateReportRequest:
    bundle = CaseEvidenceBundle(
        case_id=record.case.id,
        case_summary=record.description or record.case.intake_summary or record.case.title,
        evidence_items=[
            _build_enriched_evidence_item(item)
            for item in record.case.evidence
        ],
        event_candidates=_derive_event_candidates(record.case.evidence),
        entities=[
            EntityMention(
                entity_id=entity.id,
                name=entity.name,
                role=entity.type,
                description=_entity_description(entity),
            )
            for entity in record.case.entities
        ],
    )
    return GenerateReportRequest(
        bundle=bundle,
        user_id=user_id,
        enable_public_context=enable_public_context,
        max_images=max_images,
        max_reconstructions=max_reconstructions,
    )


def _build_enriched_evidence_item(item: LegacyEvidenceItem):
    base = CaseWorkspaceService._to_report_evidence_item(item)
    source_spans = _build_source_spans(item)
    metadata = _build_evidence_metadata(item)
    return base.model_copy(
        update={
            "source_spans": source_spans,
            "metadata": metadata,
        }
    )


def _build_source_spans(item: LegacyEvidenceItem) -> list[SourceSpan]:
    analysis = getattr(item, "_analysis", None) or {}
    spans: list[SourceSpan] = []
    seen: set[tuple[Any, ...]] = set()

    for index, fact in enumerate(analysis.get("key_facts", []), start=1):
        span = _source_span_from_analysis_item(
            segment_id=f"{item.id}:fact:{index}",
            uri=item.media.url,
            analysis_item=fact,
            default_snippet=fact.get("excerpt") or fact.get("fact"),
        )
        if span is not None:
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

    for index, event in enumerate(analysis.get("timeline_events", []), start=1):
        span = _source_span_from_analysis_item(
            segment_id=f"{item.id}:timeline:{index}",
            uri=item.media.url,
            analysis_item=event,
            default_snippet=event.get("description"),
        )
        if span is not None:
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


def _source_span_from_analysis_item(
    *,
    segment_id: str,
    uri: str | None,
    analysis_item: dict[str, Any],
    default_snippet: str | None,
) -> SourceSpan | None:
    page_number = _as_positive_int(analysis_item.get("page"))

    timestamp_ms: list[int] | None = None
    if analysis_item.get("timestamp_start") is not None:
        start_ms = _seconds_to_ms(analysis_item.get("timestamp_start"))
        end_source = analysis_item.get("timestamp_end", analysis_item.get("timestamp_start"))
        end_ms = _seconds_to_ms(end_source)
        if start_ms is not None and end_ms is not None:
            timestamp_ms = [start_ms, max(start_ms, end_ms)]
    elif analysis_item.get("mentioned_at") is not None:
        point_ms = _seconds_to_ms(analysis_item.get("mentioned_at"))
        if point_ms is not None:
            timestamp_ms = [point_ms, point_ms]

    snippet = _clean_text(default_snippet)
    if not page_number and not timestamp_ms and not snippet:
        return None

    return SourceSpan(
        segment_id=segment_id,
        page_number=page_number,
        time_range_ms=timestamp_ms,
        snippet=snippet,
        uri=uri,
    )


def _build_evidence_metadata(item: LegacyEvidenceItem) -> dict[str, Any]:
    analysis = getattr(item, "_analysis", None) or {}
    return {
        "legacy_evidence_type": getattr(item.evidence_type, "value", item.evidence_type),
        "labels": list(item.labels),
        "analysis_summary": analysis.get("summary") or item.summary,
        "entity_names": [entity.name for entity in item.entities],
        "key_facts": analysis.get("key_facts", []),
        "timeline_events": analysis.get("timeline_events", []),
    }


def _derive_event_candidates(evidence_items: list[LegacyEvidenceItem]) -> list[EventCandidate]:
    candidates: list[EventCandidate] = []
    for evidence_index, item in enumerate(evidence_items, start=1):
        analysis = getattr(item, "_analysis", None) or {}
        timeline_events = analysis.get("timeline_events", [])
        for event_index, event in enumerate(timeline_events, start=1):
            description = _clean_text(event.get("description"))
            if not description:
                continue
            timestamp_label = _clean_text(event.get("timestamp"))
            scene_description = _scene_description_for_event(description)
            image_prompt_hint = _image_prompt_hint_for_event(description)
            candidates.append(
                EventCandidate(
                    event_id=f"{item.id}-event-{event_index}",
                    title=_title_for_event(description),
                    description=description,
                    sort_key=f"{evidence_index:04d}-{event_index:04d}",
                    timestamp_label=timestamp_label,
                    evidence_refs=[item.id],
                    scene_description=scene_description,
                    image_prompt_hint=image_prompt_hint,
                    reference_image_uris=_reference_image_uris(item),
                    public_context_queries=_public_context_queries(description, item.labels),
                )
            )
    return candidates


def _title_for_event(description: str) -> str:
    normalized = description.lower()
    title_rules = (
        ("signal state", ("signal", "light was", "yellow", "green", "red")),
        ("pre-incident positioning", ("waiting", "stopped", "standing", "position", "left-turn lane")),
        ("entry into conflict zone", ("entered", "committed to the turn", "started moving", "started its left turn", "stepped into")),
        ("obstruction or line of sight", ("blocked", "obstruction", "line of sight", "could see", "view")),
        ("collision point", ("impact", "collision", "struck", "hit")),
        ("post-incident positions", ("after the crash", "after impact", "came to rest", "ended up", "rolled toward")),
        ("body position", ("body", "fell", "floor", "stair", "stairs", "lying")),
        ("hazard layout", ("hazard", "glass", "chair", "bag", "door", "counter", "aisle")),
    )
    for title, keywords in title_rules:
        if any(keyword in normalized for keyword in keywords):
            return title
    words = description.split()
    return " ".join(words[:8]) if len(words) > 8 else description


def _scene_description_for_event(description: str) -> str:
    return (
        "Evidence-grounded reconstruction of the reported scene moment. "
        f"{description}"
    )


def _image_prompt_hint_for_event(description: str) -> str | None:
    normalized = description.lower()
    if any(token in normalized for token in ("signal", "yellow", "green", "red light", "traffic light")):
        return (
            "Text-free, diagrammatic top-down view of the intersection showing the traffic signal "
            "state and the relevant vehicles' positions just before entry."
        )
    if any(token in normalized for token in ("line of sight", "blocked", "view", "could see")):
        return (
            "Text-free first-person witness-view still showing the obstruction and what was visible "
            "from that vantage point."
        )
    if any(token in normalized for token in ("waiting", "standing", "position", "stopped", "left-turn lane")):
        return (
            "Text-free, diagrammatic still showing the static positioning of the relevant people and "
            "vehicles."
        )
    if any(token in normalized for token in ("after the crash", "after impact", "came to rest", "ended up", "body", "fell", "lying")):
        return (
            "Text-free, diagrammatic still showing final body or vehicle positions relative to the "
            "surrounding scene."
        )
    if any(token in normalized for token in ("hazard", "glass", "chair", "door", "counter", "aisle", "stairs", "stairwell")):
        return (
            "Text-free, diagrammatic still clarifying the hazard or object layout within the scene."
        )
    return None


def _reference_image_uris(item: LegacyEvidenceItem) -> list[str]:
    kind = _map_legacy_evidence_type(item.evidence_type)
    if kind.value == "image" and item.media.url:
        return [item.media.url]
    return []


def _public_context_queries(description: str, labels: list[str]) -> list[str]:
    normalized = description.lower()
    lowered_labels = {label.lower() for label in labels}
    queries: list[str] = []
    if any(token in normalized for token in ("signal", "intersection", "crosswalk")) or {
        "traffic_accident",
        "intersection",
    } & lowered_labels:
        queries.append("signalized intersection traffic-control context")
    if any(token in normalized for token in ("line of sight", "blocked", "view", "visibility")):
        queries.append("line-of-sight and visibility context for a roadway witness viewpoint")
    return queries[:3]


def _entity_description(entity: Any) -> str | None:
    mention_count = len(getattr(entity, "mentions", []))
    aliases = list(getattr(entity, "aliases", []) or [])
    parts: list[str] = []
    if aliases:
        parts.append(f"Aliases: {', '.join(aliases)}.")
    parts.append(f"Source mentions: {mention_count}.")
    return " ".join(parts) if parts else None


def _build_parser_analysis_summary(record: CaseWorkspaceRecord) -> dict[str, Any]:
    evidence_items: list[dict[str, Any]] = []
    for item in record.case.evidence:
        analysis = getattr(item, "_analysis", None) or {}
        evidence_items.append(
            {
                "evidence_id": item.id,
                "filename": item.filename,
                "legacy_evidence_type": getattr(item.evidence_type, "value", item.evidence_type),
                "labels": list(item.labels),
                "summary": item.summary,
                "entity_names": [entity.name for entity in item.entities],
                "analysis_fields": sorted(analysis.keys()),
                "key_fact_count": len(analysis.get("key_facts", [])),
                "timeline_event_count": len(analysis.get("timeline_events", [])),
                "key_facts": analysis.get("key_facts", []),
                "timeline_events": analysis.get("timeline_events", []),
            }
        )
    return {
        "case_id": record.case.id,
        "evidence_item_count": len(evidence_items),
        "evidence_items": evidence_items,
    }


def _build_comparison_summary(
    current_request: GenerateReportRequest,
    enriched_request: GenerateReportRequest,
    record: CaseWorkspaceRecord,
) -> dict[str, Any]:
    current_bundle = current_request.bundle
    enriched_bundle = enriched_request.bundle
    return {
        "evidence_item_count": len(current_bundle.evidence_items),
        "entity_count": len(current_bundle.entities),
        "current_event_candidate_count": len(current_bundle.event_candidates),
        "enriched_event_candidate_count": len(enriched_bundle.event_candidates),
        "current_evidence_fields_present": _present_evidence_fields(current_bundle.evidence_items),
        "enriched_evidence_fields_present": _present_evidence_fields(enriched_bundle.evidence_items),
        "parser_analysis_fields_detected": sorted(
            {
                key
                for item in record.case.evidence
                for key in ((getattr(item, "_analysis", None) or {}).keys())
            }
        ),
    }


def _present_evidence_fields(evidence_items: list[Any]) -> list[str]:
    fields = set()
    for item in evidence_items:
        payload = item.model_dump(mode="json")
        for key, value in payload.items():
            if value not in (None, "", [], {}):
                fields.add(key)
    return sorted(fields)


def _build_derived_event_summary(enriched_request: GenerateReportRequest) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for event in enriched_request.bundle.event_candidates:
        summary.append(
            {
                "event_id": event.event_id,
                "title": event.title,
                "timestamp_label": event.timestamp_label,
                "evidence_refs": list(event.evidence_refs),
                "suggested_primary_media": "image" if event.image_prompt_hint else "video_or_text",
                "scene_description_present": bool(event.scene_description),
                "image_prompt_hint_present": bool(event.image_prompt_hint),
                "public_context_queries": list(event.public_context_queries),
            }
        )
    return summary


def _parse_optional_bool(raw_value: str) -> bool | None:
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    return None


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


if __name__ == "__main__":
    raise SystemExit(main())
