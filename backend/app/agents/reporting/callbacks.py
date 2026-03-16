from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.agents.reporting.progress import ProgressEventBuffer
from app.agents.reporting.types import (
    ComposerOutput,
    ContextNote,
    ContextPlan,
    ReportGenerationPolicy,
    TimelinePlan,
)
from app.agents.reporting.validators import normalize_composer_output, validate_composer_output
from app.models import CaseEvidenceBundle, ReportProvenance
from app.services.generation.report_citations import (
    build_public_context_citation,
    normalize_citation,
)

CONTEXT_PLAN_STATE = "context_plan_json"
REPORTING_WARNINGS_STATE = "reporting_warnings_json"
_CONTEXT_WARNING_PREFIX = "Public-context enrichment omitted:"


def before_model_guard(callback_context: Any, llm_request: Any) -> Any | None:
    policy = _load_state_model(
        callback_context.state,
        key="generation_policy_json",
        model_type=ReportGenerationPolicy,
    )
    prefix = (
        "Clarion policy:\n"
        f"- Evidence chronology must remain evidence-grounded.\n"
        f"- Public context enabled: {policy.enable_public_context}.\n"
        f"- Max images: {policy.max_images}.\n"
        f"- Max reconstructions: {policy.max_reconstructions}.\n"
        "- Never mix public context citations into evidence blocks.\n"
    )

    current_text = _coerce_instruction_text(llm_request.config.system_instruction)
    llm_request.config.system_instruction = f"{prefix}\n{current_text}".strip()
    return None


def after_context_model_guard(callback_context: Any, llm_response: Any) -> Any | None:
    policy = _load_state_model(
        callback_context.state,
        key="generation_policy_json",
        model_type=ReportGenerationPolicy,
    )
    timeline = _load_state_model(
        callback_context.state,
        key="timeline_plan_json",
        model_type=TimelinePlan,
    )

    warnings: list[str] = []
    if not policy.enable_public_context or not _timeline_requests_public_context(timeline):
        context_plan = ContextPlan()
    else:
        response_text = _extract_text(llm_response)
        if not response_text:
            context_plan = ContextPlan()
            warnings.append(
                f"{_CONTEXT_WARNING_PREFIX} empty ContextPlan output."
            )
        else:
            context_plan, warnings = _parse_context_plan_response(response_text, timeline)

    callback_context.state[CONTEXT_PLAN_STATE] = context_plan.model_dump(
        mode="json",
        exclude_none=True,
    )
    _store_reporting_warnings(callback_context.state, warnings)
    return None


def after_model_guard(callback_context: Any, llm_response: Any) -> Any | None:
    agent_name = getattr(callback_context, "agent_name", "")
    if agent_name not in {"FinalComposerAgent", "CompositionRefinerAgent"}:
        return None

    response_text = _extract_text(llm_response)
    if not response_text:
        return None

    _load_state_model(
        callback_context.state,
        key="case_bundle_json",
        model_type=CaseEvidenceBundle,
    )
    timeline = _load_state_model(
        callback_context.state,
        key="timeline_plan_json",
        model_type=TimelinePlan,
    )
    output = _parse_response_model(response_text, ComposerOutput)
    output = normalize_composer_output(output, timeline)
    issues = validate_composer_output(output)
    if issues:
        raise ValueError("; ".join(issues))
    return None


def _extract_text(llm_response: Any) -> str:
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None) or []
    text_parts: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            text_parts.append(str(text))
    return "".join(text_parts).strip()


def _parse_response_model(payload: str, model_type: type[BaseModel]) -> BaseModel:
    try:
        return model_type.model_validate_json(payload)
    except Exception:
        return model_type.model_validate(json.loads(payload))


def _parse_context_plan_response(
    payload: str,
    timeline: TimelinePlan,
) -> tuple[ContextPlan, list[str]]:
    normalized_payload = _strip_markdown_fences(payload)
    try:
        raw_payload = json.loads(normalized_payload)
    except Exception as exc:
        return (
            ContextPlan(),
            [
                (
                    f"{_CONTEXT_WARNING_PREFIX} invalid ContextPlan payload. "
                    f"Output preview: {_preview_text(normalized_payload)}"
                )
            ],
        )
    return _coerce_context_plan(raw_payload, timeline, output_preview=normalized_payload)


def _load_state_model(
    state: dict[str, Any],
    *,
    key: str,
    model_type: type[BaseModel],
) -> BaseModel:
    value = state.get(key)
    if isinstance(value, model_type):
        return value
    if isinstance(value, str):
        try:
            return model_type.model_validate_json(value)
        except Exception:
            return model_type.model_validate(json.loads(value))
    return model_type.model_validate(value or {})


def _coerce_instruction_text(instruction: Any) -> str:
    if instruction is None:
        return ""
    if isinstance(instruction, str):
        return instruction

    parts = getattr(instruction, "parts", None)
    if parts:
        text_parts: list[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(str(text))
        if text_parts:
            return "\n".join(text_parts)

    if isinstance(instruction, list):
        text_parts = []
        for item in instruction:
            coerced = _coerce_instruction_text(item)
            if coerced:
                text_parts.append(coerced)
        return "\n".join(text_parts)

    text = getattr(instruction, "text", None)
    if text:
        return str(text)

    return str(instruction)


def _timeline_requests_public_context(timeline: TimelinePlan) -> bool:
    return any(event.public_context_queries for event in timeline.timeline_events)


def _coerce_context_plan(
    payload: object,
    timeline: TimelinePlan,
    *,
    output_preview: str,
) -> tuple[ContextPlan, list[str]]:
    raw_notes: object
    if isinstance(payload, list):
        raw_notes = payload
    elif isinstance(payload, dict):
        note_key = next(
            (
                key
                for key in ("notes", "context_notes", "public_context_notes")
                if key in payload
            ),
            None,
        )
        if note_key is None:
            return (
                ContextPlan(),
                [
                    (
                        f"{_CONTEXT_WARNING_PREFIX} invalid ContextPlan payload. "
                        f"Output preview: {_preview_text(output_preview)}"
                    )
                ],
            )
        raw_notes = payload.get(note_key)
    else:
        return (
            ContextPlan(),
            [
                (
                    f"{_CONTEXT_WARNING_PREFIX} invalid ContextPlan payload. "
                    f"Output preview: {_preview_text(output_preview)}"
                )
            ],
        )

    if not isinstance(raw_notes, list):
        return (
            ContextPlan(),
            [
                (
                    f"{_CONTEXT_WARNING_PREFIX} invalid ContextPlan payload. "
                    f"Output preview: {_preview_text(output_preview)}"
                )
            ],
        )

    notes: list[ContextNote] = []
    warnings: list[str] = []
    matched_counts: dict[str, int] = {}
    fallback_count = 0
    fallback_sort_base = _fallback_context_sort_base(timeline)

    for note_index, raw_note in enumerate(raw_notes, start=1):
        raw_sort_key = raw_note.get("sort_key") if isinstance(raw_note, dict) else None
        normalized_note, warning, matched_event_id = _coerce_context_note(
            raw_note,
            timeline=timeline,
            note_index=note_index,
            matched_counts=matched_counts,
            fallback_sort_base=fallback_sort_base,
            fallback_count=fallback_count,
        )
        if matched_event_id is None and normalized_note is not None and not _clean_sort_key(
            raw_sort_key
        ):
            fallback_count += 1
        if warning is not None:
            warnings.append(warning)
        if normalized_note is not None:
            notes.append(normalized_note)

    if not notes and raw_notes:
        if warnings:
            return ContextPlan(), warnings
        return (
            ContextPlan(),
            [
                (
                    f"{_CONTEXT_WARNING_PREFIX} invalid ContextPlan payload. "
                    f"Output preview: {_preview_text(output_preview)}"
                )
            ],
        )

    return ContextPlan(notes=notes), warnings


def _coerce_context_note(
    raw_note: object,
    *,
    timeline: TimelinePlan,
    note_index: int,
    matched_counts: dict[str, int],
    fallback_sort_base: str,
    fallback_count: int,
) -> tuple[ContextNote | None, str | None, str | None]:
    if not isinstance(raw_note, dict):
        return None, f"{_CONTEXT_WARNING_PREFIX} dropped 1 malformed public-context note.", None

    title = _clean_text(
        raw_note.get("title")
        or raw_note.get("topic")
    )
    content = _clean_text(
        raw_note.get("content")
        or raw_note.get("summary")
    )
    if title is None or content is None:
        return None, f"{_CONTEXT_WARNING_PREFIX} dropped 1 malformed public-context note.", None

    matched_event = _match_context_event(raw_note, timeline)
    citations = _normalize_context_citations(
        raw_note,
        note_content=content,
        note_index=note_index,
    )
    if not citations:
        return (
            None,
            f"{_CONTEXT_WARNING_PREFIX} dropped 1 ungrounded public-context note.",
            matched_event.event_id if matched_event is not None else None,
        )

    explicit_sort_key = _clean_sort_key(raw_note.get("sort_key"))
    if explicit_sort_key is not None:
        sort_key = explicit_sort_key
        matched_event_id = matched_event.event_id if matched_event is not None else None
    elif matched_event is not None:
        offset = matched_counts.get(matched_event.event_id, 0)
        matched_counts[matched_event.event_id] = offset + 1
        sort_key = f"{matched_event.sort_key}.{5 + offset:03d}"
        matched_event_id = matched_event.event_id
    else:
        sort_key = f"{fallback_sort_base}.{80 + fallback_count:03d}"
        matched_event_id = None

    confidence_score = _coerce_confidence(
        raw_note.get("confidence_score", raw_note.get("confidence"))
    )
    note = ContextNote(
        title=title,
        content=content,
        sort_key=sort_key,
        citations=citations,
        confidence_score=confidence_score,
    )
    return note, None, matched_event_id


def _normalize_context_citations(
    raw_note: dict[str, Any],
    *,
    note_content: str,
    note_index: int,
) -> list[Any]:
    citations: list[Any] = []
    raw_citations = raw_note.get("citations")
    if isinstance(raw_citations, list):
        for raw_citation in raw_citations:
            normalized = _normalize_existing_context_citation(
                raw_citation,
                fallback_excerpt=note_content,
            )
            if normalized is not None:
                citations.append(normalized)

    if citations:
        return _dedupe_citations(citations)

    raw_sources = (
        raw_note.get("sources")
        or raw_note.get("search_results")
        or raw_note.get("results")
        or []
    )
    if not isinstance(raw_sources, list):
        return []

    for source_index, raw_source in enumerate(raw_sources, start=1):
        normalized = _build_context_citation_from_source(
            raw_source,
            note_content=note_content,
            note_index=note_index,
            source_index=source_index,
        )
        if normalized is not None:
            citations.append(normalized)

    return _dedupe_citations(citations)


def _normalize_existing_context_citation(
    raw_citation: object,
    *,
    fallback_excerpt: str,
):
    try:
        if isinstance(raw_citation, dict):
            source_id = _clean_text(raw_citation.get("source_id"))
            if source_id is None:
                source_id = _clean_text(
                    raw_citation.get("uri")
                    or raw_citation.get("url")
                    or raw_citation.get("title")
                )
            if source_id is None:
                return None
            citation = normalize_citation(
                build_public_context_citation(
                    source_id,
                    source_label=_clean_text(
                        raw_citation.get("source_label") or raw_citation.get("title")
                    ),
                    excerpt=_clean_text(
                        raw_citation.get("excerpt") or raw_citation.get("snippet")
                    ),
                    uri=_clean_text(raw_citation.get("uri") or raw_citation.get("url")),
                    fallback_excerpt=fallback_excerpt,
                ),
                provenance=ReportProvenance.public_context,
                fallback_excerpt=fallback_excerpt,
            )
            return citation

        citation = normalize_citation(
            raw_citation.model_copy(update={"provenance": ReportProvenance.public_context}),
            provenance=ReportProvenance.public_context,
            fallback_excerpt=fallback_excerpt,
        )
        return citation
    except Exception:
        return None


def _build_context_citation_from_source(
    raw_source: object,
    *,
    note_content: str,
    note_index: int,
    source_index: int,
):
    if isinstance(raw_source, str):
        source_label = _clean_text(raw_source)
        if source_label is None:
            return None
        return build_public_context_citation(
            f"public-context-{note_index}-{source_index}",
            source_label=source_label,
            fallback_excerpt=note_content,
        )

    if not isinstance(raw_source, dict):
        return None

    source_id = _clean_text(
        raw_source.get("source_id")
        or raw_source.get("id")
        or raw_source.get("uri")
        or raw_source.get("url")
        or raw_source.get("title")
        or f"public-context-{note_index}-{source_index}"
    )
    if source_id is None:
        return None

    return build_public_context_citation(
        source_id,
        source_label=_clean_text(
            raw_source.get("source_label")
            or raw_source.get("title")
            or raw_source.get("name")
        ),
        excerpt=_clean_text(
            raw_source.get("excerpt")
            or raw_source.get("snippet")
            or raw_source.get("content")
            or raw_source.get("summary")
        ),
        uri=_clean_text(raw_source.get("uri") or raw_source.get("url") or raw_source.get("link")),
        fallback_excerpt=note_content,
    )


def _dedupe_citations(citations: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for citation in citations:
        key = (citation.source_id, citation.uri, citation.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _match_context_event(raw_note: dict[str, Any], timeline: TimelinePlan):
    candidate_texts = [
        raw_note.get("title"),
        raw_note.get("topic"),
        raw_note.get("query"),
        raw_note.get("search_query"),
        raw_note.get("content"),
        raw_note.get("summary"),
    ]
    normalized_texts = [
        _normalize_match_text(value)
        for value in candidate_texts
        if _normalize_match_text(value)
    ]
    if not normalized_texts:
        return None

    best_event = None
    best_score = 0
    for event in timeline.timeline_events:
        for query in event.public_context_queries:
            normalized_query = _normalize_match_text(query)
            if not normalized_query:
                continue
            for text in normalized_texts:
                score = _context_match_score(normalized_query, text)
                if score > best_score:
                    best_score = score
                    best_event = event
    return best_event if best_score > 0 else None


def _context_match_score(query: str, text: str) -> int:
    if text == query:
        return 4
    if query in text or text in query:
        return 3

    query_tokens = {token for token in query.split() if len(token) > 3}
    text_tokens = set(text.split())
    overlap = len(query_tokens & text_tokens)
    if overlap >= 2:
        return 2
    if overlap == 1:
        return 1
    return 0


def _fallback_context_sort_base(timeline: TimelinePlan) -> str:
    if not timeline.timeline_events:
        return "9999"
    return max((event.sort_key for event in timeline.timeline_events), default="9999")


def _normalize_match_text(value: object) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    return " ".join(text.casefold().split())


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_sort_key(value: object) -> str | None:
    text = _clean_text(value)
    return text


def _coerce_confidence(value: object) -> float:
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, numeric))


def _store_reporting_warnings(state: Any, warnings: list[str]) -> None:
    existing = state.get(REPORTING_WARNINGS_STATE, [])
    if not isinstance(existing, list):
        existing = list(existing) if existing else []
    merged = list(existing)
    for warning in warnings:
        if warning and warning not in merged:
            merged.append(warning)
    state[REPORTING_WARNINGS_STATE] = merged


def _strip_markdown_fences(payload: str) -> str:
    text = payload.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if not lines:
        return text
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _preview_text(payload: str, *, limit: int = 240) -> str:
    compact = " ".join(payload.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def build_progress_callbacks(
    progress_events: ProgressEventBuffer | None,
    *,
    include_tool_detail: bool = False,
) -> dict[str, Any]:
    if progress_events is None:
        return {}

    def before_agent_progress(callback_context: Any) -> Any | None:
        progress_events.agent_started(getattr(callback_context, "agent_name", ""))
        return None

    def after_agent_progress(callback_context: Any) -> Any | None:
        progress_events.agent_completed(getattr(callback_context, "agent_name", ""))
        return None

    def on_model_error(
        callback_context: Any,
        llm_request: Any,
        error: Exception | None = None,
        exc: Exception | None = None,
        **_: Any,
    ) -> Any | None:
        del llm_request
        progress_events.agent_failed(
            getattr(callback_context, "agent_name", ""),
            _stringify_error(error or exc),
        )
        return None

    callbacks = {
        "before_agent_callback": before_agent_progress,
        "after_agent_callback": after_agent_progress,
        "on_model_error_callback": on_model_error,
    }

    if include_tool_detail:
        def before_tool_progress(
            tool: Any,
            args: dict[str, Any],
            tool_context: Any = None,
            **_: Any,
        ) -> Any | None:
            tool_name = getattr(tool, "name", tool.__class__.__name__)
            progress_events.tool_started(
                getattr(tool_context, "agent_name", ""),
                tool_name,
                args,
            )
            return None

        def on_tool_error(
            tool: Any,
            args: dict[str, Any],
            tool_context: Any = None,
            error: Exception | None = None,
            exc: Exception | None = None,
            **_: Any,
        ) -> Any | None:
            del args
            tool_name = getattr(tool, "name", tool.__class__.__name__)
            progress_events.tool_failed(
                getattr(tool_context, "agent_name", ""),
                tool_name,
                _stringify_error(error or exc),
            )
            return None

        callbacks.update(
            {
                "before_tool_callback": before_tool_progress,
                "on_tool_error_callback": on_tool_error,
            }
        )

    return callbacks


def _stringify_error(error: Exception | None) -> str:
    if error is None:
        return "Unknown callback error"
    return str(error)
