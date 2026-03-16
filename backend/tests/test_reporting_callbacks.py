from types import SimpleNamespace

from app.agents.reporting.callbacks import build_progress_callbacks
from app.agents.reporting.progress import ProgressEventBuffer


def test_progress_callbacks_accept_adk_keyword_arguments():
    buffer = ProgressEventBuffer()
    callbacks = build_progress_callbacks(buffer, include_tool_detail=True)

    callbacks["before_tool_callback"](
        tool=SimpleNamespace(name="google_search"),
        args={"query": "intersection collision"},
        tool_context=SimpleNamespace(agent_name="ContextEnrichmentAgent"),
    )
    callbacks["on_tool_error_callback"](
        tool=SimpleNamespace(name="google_search"),
        args={"query": "intersection collision"},
        tool_context=SimpleNamespace(agent_name="ContextEnrichmentAgent"),
        error=RuntimeError("search failed"),
    )
    callbacks["on_model_error_callback"](
        callback_context=SimpleNamespace(agent_name="FinalComposerAgent"),
        llm_request=object(),
        error=RuntimeError("composer failed"),
    )

    events = buffer.drain()
    assert [event.kind for event in events] == [
        "node_detail",
        "node_detail",
        "node_failed",
    ]
    assert events[1].detail == "google_search failed: search failed"
    assert events[2].detail == "composer failed"
