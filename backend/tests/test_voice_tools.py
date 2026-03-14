from app.services.voice.models import (
    VoiceContradiction,
    VoiceEntity,
    VoiceEvidence,
    VoiceMention,
    VoiceReportSection,
    VoiceSessionContext,
)
from app.services.voice.tools import execute_tool, get_tool_declarations


def _make_context() -> VoiceSessionContext:
    return VoiceSessionContext(
        report_id="report-1",
        case_id="case-1",
        title="Smith v. Johnson",
        case_type="personal_injury",
        status="completed",
        evidence=[
            VoiceEvidence(
                evidence_id="ev_001",
                filename="police_report.pdf",
                evidence_type="police_report",
                summary="Police report",
                content_text="Officer observed rear-end damage to plaintiff vehicle.",
                media_url="file:///tmp/police.pdf",
            )
        ],
        entities=[
            VoiceEntity(
                entity_id="ent_001",
                entity_type="person",
                name="John Smith",
                mentions=[
                    VoiceMention(
                        evidence_id="ev_001",
                        page=1,
                        excerpt="John Smith",
                    )
                ],
            )
        ],
        contradictions=[
            VoiceContradiction(
                contradiction_id="c_001",
                severity="high",
                description="Speed disputed - John Smith",
                fact_a="John Smith says 25 mph",
                fact_b="Police report says 40 mph",
            )
        ],
        sections=[
            VoiceReportSection(
                section_id="s_001",
                kind="text",
                title="Collision Summary",
                text="Original text",
            )
        ],
    )


def test_get_tool_declarations_returns_tool():
    tool = get_tool_declarations()
    assert tool is not None
    assert len(tool.function_declarations) == 4


def test_execute_navigate_to():
    context = _make_context()
    result, frontend_event = execute_tool(
        "navigate_to",
        {"target": "contradiction", "id": "c_001"},
        context,
    )
    assert "Navigated to contradiction c_001" in result
    assert frontend_event == {
        "type": "navigate",
        "target": "contradiction",
        "id": "c_001",
    }


def test_execute_query_evidence():
    context = _make_context()
    result, frontend_event = execute_tool(
        "query_evidence",
        {"evidence_id": "ev_001"},
        context,
    )
    assert "Officer observed" in result
    assert frontend_event is None


def test_execute_query_evidence_not_found():
    context = _make_context()
    result, frontend_event = execute_tool(
        "query_evidence",
        {"evidence_id": "nonexistent"},
        context,
    )
    assert "not found" in result.lower()
    assert frontend_event is None


def test_execute_get_entity_detail():
    context = _make_context()
    result, frontend_event = execute_tool(
        "get_entity_detail",
        {"entity_name": "John Smith"},
        context,
    )
    assert "John Smith" in result
    assert "person" in result
    assert "Contradictions: 1" in result
    assert frontend_event is None


def test_execute_get_entity_detail_case_insensitive():
    context = _make_context()
    result, _ = execute_tool(
        "get_entity_detail",
        {"entity_name": "john smith"},
        context,
    )
    assert "John Smith" in result


def test_execute_edit_section():
    context = _make_context()
    result, frontend_event = execute_tool(
        "edit_section",
        {"section_id": "s_001", "instruction": "make it shorter"},
        context,
    )
    assert "Edit request submitted" in result
    assert frontend_event["type"] == "edit_result"
    assert frontend_event["section_id"] == "s_001"
    assert frontend_event["status"] == "success"
