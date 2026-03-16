from types import SimpleNamespace

from app.agents.reporting.callbacks import (
    REPORTING_WARNINGS_STATE,
    after_context_model_guard,
)
from app.agents.reporting.types import ContextPlan, ReportGenerationPolicy, TimelineEvent, TimelinePlan
from app.models import ReportProvenance


def _callback_context(*, enable_public_context: bool = True, with_queries: bool = True):
    policy = ReportGenerationPolicy(
        text_model="gemini-3-pro-preview",
        helper_model="gemini-3-flash-preview",
        image_model="gemini-3-pro-image-preview",
        search_model="gemini-2.5-flash",
        enable_public_context=enable_public_context,
    )
    timeline = TimelinePlan(
        timeline_events=[
            TimelineEvent(
                event_id="signal",
                title="Signal timing",
                narrative="The signal changed as the vehicles approached.",
                sort_key="0010",
                evidence_refs=["ev-1"],
                public_context_queries=["yellow interval timing"] if with_queries else [],
            )
        ]
    )
    return SimpleNamespace(
        agent_name="ContextEnrichmentAgent",
        state={
            "generation_policy_json": policy.model_dump(mode="json"),
            "timeline_plan_json": timeline.model_dump(mode="json"),
            "context_plan_json": ContextPlan().model_dump(mode="json"),
        },
    )


def _response(text: str):
    return SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text=text)]))


def test_context_callback_writes_validated_plan_to_state():
    callback_context = _callback_context()
    payload = """
    {
      "notes": [
        {
          "title": "Signal timing context",
          "content": "Yellow interval timing depends on approach speed and grade.",
          "sort_key": "0010.05",
          "confidence_score": 0.61,
          "citations": [
            {
              "source_id": "ctx-1",
              "source_label": "FHWA Signal Timing Manual",
              "excerpt": "Yellow change intervals depend on speed and grade.",
              "provenance": "evidence"
            }
          ]
        }
      ]
    }
    """

    after_context_model_guard(callback_context, _response(payload))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert stored.notes[0].title == "Signal timing context"
    assert stored.notes[0].citations[0].provenance == ReportProvenance.public_context
    assert callback_context.state[REPORTING_WARNINGS_STATE] == []


def test_context_callback_accepts_fenced_json():
    callback_context = _callback_context()
    payload = """
    ```json
    {
      "notes": [
        {
          "title": "Visibility context",
          "content": "Street lighting can improve witness visibility at night.",
          "sort_key": "0020.05",
          "confidence_score": 0.5,
          "citations": [
            {
              "source_id": "ctx-2",
              "source_label": "Lighting Guidance",
              "excerpt": "Street lighting improves night-time visibility.",
              "provenance": "public_context"
            }
          ]
        }
      ]
    }
    ```
    """

    after_context_model_guard(callback_context, _response(payload))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert stored.notes[0].sort_key == "0020.05"

def test_context_callback_normalizes_legacy_context_note_payload():
    callback_context = _callback_context()
    payload = """
    {
      "context_notes": [
        {
          "note_id": "ctx-note-1",
          "topic": "Signal timing context",
          "summary": "Yellow interval timing depends on approach speed and grade.",
          "confidence": 0.71,
          "sources": [
            {
              "title": "FHWA Signal Timing Manual",
              "url": "https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm",
              "snippet": "Yellow change intervals depend on speed and grade."
            }
          ]
        }
      ]
    }
    """

    after_context_model_guard(callback_context, _response(payload))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert len(stored.notes) == 1
    assert stored.notes[0].title == "Signal timing context"
    assert stored.notes[0].content == "Yellow interval timing depends on approach speed and grade."
    assert stored.notes[0].sort_key == "0010.005"
    assert stored.notes[0].confidence_score == 0.71
    assert stored.notes[0].citations[0].provenance == ReportProvenance.public_context
    assert stored.notes[0].citations[0].source_label == "FHWA Signal Timing Manual"
    assert callback_context.state[REPORTING_WARNINGS_STATE] == []


def test_context_callback_omits_invalid_payload_with_warning():
    callback_context = _callback_context()

    after_context_model_guard(callback_context, _response("not valid json at all"))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert stored.notes == []
    warnings = callback_context.state[REPORTING_WARNINGS_STATE]
    assert len(warnings) == 1
    assert warnings[0].startswith("Public-context enrichment omitted: invalid ContextPlan payload.")
    assert "Output preview: not valid json at all" in warnings[0]


def test_context_callback_drops_ungrounded_note_but_keeps_valid_one():
    callback_context = _callback_context()
    payload = """
    {
      "notes": [
        {
          "topic": "Ungrounded context",
          "summary": "This note has no public source data.",
          "confidence": 0.2
        },
        {
          "title": "Signal timing context",
          "content": "Yellow interval timing depends on approach speed and grade.",
          "confidence_score": 0.74,
          "sources": [
            {
              "title": "FHWA Signal Timing Manual",
              "url": "https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm",
              "snippet": "Yellow change intervals depend on speed and grade."
            }
          ]
        }
      ]
    }
    """

    after_context_model_guard(callback_context, _response(payload))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert len(stored.notes) == 1
    assert stored.notes[0].title == "Signal timing context"
    warnings = callback_context.state[REPORTING_WARNINGS_STATE]
    assert any("dropped 1 ungrounded public-context note." in warning for warning in warnings)


def test_context_callback_returns_empty_plan_when_no_queries_are_present():
    callback_context = _callback_context(with_queries=False)

    after_context_model_guard(callback_context, _response(""))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert stored.notes == []
    assert callback_context.state[REPORTING_WARNINGS_STATE] == []


def test_context_callback_returns_empty_plan_when_public_context_is_disabled():
    callback_context = _callback_context(enable_public_context=False)

    after_context_model_guard(callback_context, _response("not json"))

    stored = ContextPlan.model_validate(callback_context.state["context_plan_json"])
    assert stored.notes == []
    assert callback_context.state[REPORTING_WARNINGS_STATE] == []
