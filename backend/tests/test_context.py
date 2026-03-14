"""Tests for voice context builder."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.voice.context import build_system_prompt
from app.models.schema import (
    CaseFile, EvidenceItem, ExtractedContent, MediaRef,
    Entity, SourceLocation, Contradiction, SourcePin,
    ReportSection,
)


def _make_case() -> CaseFile:
    """Minimal case fixture."""
    case = CaseFile(title="Smith v. Johnson", case_type="personal_injury", status="complete")
    case.evidence.append(
        EvidenceItem(
            id="ev_001",
            filename="police_report.pdf",
            evidence_type="police_report",
            media=MediaRef(url="file:///tmp/police.pdf", media_type="application/pdf"),
            content=ExtractedContent(text="Officer observed damage..."),
            summary="Police report documenting rear-end collision",
        )
    )
    case.entities.append(
        Entity(id="ent_001", type="person", name="John Smith", mentions=[
            SourceLocation(evidence_id="ev_001", page=1, excerpt="John Smith, plaintiff"),
        ])
    )
    case.contradictions.append(
        Contradiction(
            id="c_001",
            severity="high",
            description="Speed at impact disputed",
            source_a=SourcePin(evidence_id="ev_001", detail="Page 2", excerpt="25 mph"),
            source_b=SourcePin(evidence_id="ev_002", detail="Page 1", excerpt="40 mph"),
            fact_a="Police report states 25 mph",
            fact_b="Witness states 40 mph",
        )
    )
    case.report_sections.append(
        ReportSection(id="s_001", block_type="heading", order=0, text="Case Overview")
    )
    return case


def test_build_system_prompt_includes_case_name():
    case = _make_case()
    prompt = build_system_prompt(case)
    assert "Smith v. Johnson" in prompt


def test_build_system_prompt_includes_contradictions():
    case = _make_case()
    prompt = build_system_prompt(case)
    assert "HIGH" in prompt
    assert "25 mph" in prompt


def test_build_system_prompt_includes_entities():
    case = _make_case()
    prompt = build_system_prompt(case)
    assert "John Smith" in prompt


def test_build_system_prompt_includes_evidence():
    case = _make_case()
    prompt = build_system_prompt(case)
    assert "police_report.pdf" in prompt


def test_build_system_prompt_includes_sections():
    case = _make_case()
    prompt = build_system_prompt(case)
    assert "s_001" in prompt
    assert "Case Overview" in prompt


def test_build_system_prompt_empty_case():
    case = CaseFile(title="Empty Case", status="intake")
    prompt = build_system_prompt(case)
    assert "Empty Case" in prompt
    assert "CONTRADICTIONS" in prompt
