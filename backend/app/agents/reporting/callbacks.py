from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.agents.reporting.progress import ProgressEventBuffer
from app.agents.reporting.types import ComposerOutput, ReportGenerationPolicy, TimelinePlan
from app.agents.reporting.validators import normalize_composer_output, validate_composer_output
from app.models import CaseEvidenceBundle


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
