from app.services.voice.context import build_system_prompt
from app.services.voice.models import (
    VoiceContradiction,
    VoiceEntity,
    VoiceEvidence,
    VoiceMention,
    VoiceReportSection,
    VoiceSessionContext,
)


def test_build_system_prompt_includes_report_context_sections():
    context = VoiceSessionContext(
        report_id="report-1",
        case_id="case-1",
        title="Smith v. Johnson",
        case_type="personal_injury",
        status="completed",
        evidence=[
            VoiceEvidence(
                evidence_id="ev-1",
                filename="witness_statement.txt",
                evidence_type="witness_statement",
                summary="Witness statement",
                content_text="John Smith says the vehicle was traveling 25 mph.",
            )
        ],
        entities=[
            VoiceEntity(
                entity_id="ent-1",
                entity_type="person",
                name="John Smith",
                mentions=[
                    VoiceMention(
                        evidence_id="ev-1",
                        page=1,
                        excerpt="John Smith says the vehicle was traveling 25 mph.",
                    )
                ],
            )
        ],
        contradictions=[
            VoiceContradiction(
                contradiction_id="contr-1",
                severity="high",
                description="Speed estimate conflicts for John Smith",
                fact_a="John Smith says 25 mph",
                fact_b="Police report says 40 mph",
            )
        ],
        sections=[
            VoiceReportSection(
                section_id="section-1",
                kind="text",
                title="Collision Summary",
                text="Vehicle A struck Vehicle B from behind.",
            )
        ],
    )

    prompt = build_system_prompt(context)

    assert "CASE: Smith v. Johnson" in prompt
    assert "TYPE: personal_injury" in prompt
    assert "STATUS: completed" in prompt
    assert "CONTRADICTIONS:" in prompt
    assert "KEY ENTITIES:" in prompt
    assert "EVIDENCE FILES:" in prompt
    assert "REPORT SECTIONS:" in prompt
    assert "John Smith" in prompt
