"""Tests for voice tool declarations and execution."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.voice.tools import get_tool_declarations, execute_tool
from app.models.schema import (
    CaseFile, EvidenceItem, ExtractedContent, MediaRef,
    Entity, SourceLocation, Contradiction, SourcePin,
    ReportSection,
)


def _make_case() -> CaseFile:
    case = CaseFile(title="Smith v. Johnson", case_type="personal_injury", status="complete")
    case.evidence.append(
        EvidenceItem(
            id="ev_001",
            filename="police_report.pdf",
            evidence_type="police_report",
            media=MediaRef(url="file:///tmp/police.pdf", media_type="application/pdf"),
            content=ExtractedContent(text="Officer observed rear-end damage to plaintiff vehicle."),
            summary="Police report",
        )
    )
    case.entities.append(
        Entity(id="ent_001", type="person", name="John Smith", mentions=[
            SourceLocation(evidence_id="ev_001", page=1, excerpt="John Smith"),
        ])
    )
    case.contradictions.append(
        Contradiction(
            id="c_001", severity="high",
            description="Speed disputed — John Smith",
            source_a=SourcePin(evidence_id="ev_001", detail="p2"),
            source_b=SourcePin(evidence_id="ev_002", detail="p1"),
            fact_a="25 mph", fact_b="40 mph",
        )
    )
    return case


def test_get_tool_declarations_returns_tool():
    tool = get_tool_declarations()
    assert tool is not None
    assert len(tool.function_declarations) == 4


def test_execute_navigate_to():
    case = _make_case()
    result, frontend_event = execute_tool(
        "navigate_to", {"target": "contradiction", "id": "c_001"}, case
    )
    assert frontend_event["type"] == "navigate"
    assert frontend_event["target"] == "contradiction"
    assert frontend_event["id"] == "c_001"


def test_execute_query_evidence():
    case = _make_case()
    result, frontend_event = execute_tool(
        "query_evidence", {"evidence_id": "ev_001"}, case
    )
    assert "Officer observed" in result
    assert frontend_event is None


def test_execute_query_evidence_not_found():
    case = _make_case()
    result, frontend_event = execute_tool(
        "query_evidence", {"evidence_id": "nonexistent"}, case
    )
    assert "not found" in result.lower()


def test_execute_get_entity_detail():
    case = _make_case()
    result, frontend_event = execute_tool(
        "get_entity_detail", {"entity_name": "John Smith"}, case
    )
    assert "John Smith" in result
    assert "person" in result


def test_execute_get_entity_detail_case_insensitive():
    case = _make_case()
    result, _ = execute_tool(
        "get_entity_detail", {"entity_name": "john smith"}, case
    )
    assert "John Smith" in result


def test_execute_edit_section():
    case = _make_case()
    case.report_sections.append(
        ReportSection(id="s_001", block_type="text", order=0, text="Original text")
    )
    result, frontend_event = execute_tool(
        "edit_section", {"section_id": "s_001", "instruction": "make it shorter"}, case
    )
    assert frontend_event["type"] == "edit_result"
    assert frontend_event["section_id"] == "s_001"
