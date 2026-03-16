"""
Builds the system instruction for the Gemini Live API voice session.
Takes a report-centric voice context and produces a text prompt that tells
Gemini everything it needs to know about the current report state.
"""

from app.services.voice.models import VoiceSessionContext


def build_system_prompt(context: VoiceSessionContext) -> str:
    """Build Gemini system instruction from voice context."""
    sections = [
        _header(context),
        _contradictions(context),
        _entities(context),
        _evidence(context),
        _report_sections(context),
        _instructions(),
    ]
    return "\n\n".join(sections)


def _header(context: VoiceSessionContext) -> str:
    return (
        "You are Clarion, a litigation intelligence assistant. "
        "You speak concisely and professionally, like a sharp paralegal briefing an attorney.\n\n"
        f"CASE: {context.title or 'Untitled Case'}\n"
        f"TYPE: {context.case_type or 'Unknown'}\n"
        f"STATUS: {context.status}"
    )


def _contradictions(context: VoiceSessionContext) -> str:
    lines = ["CONTRADICTIONS:"]
    if not context.contradictions:
        lines.append("  None detected yet.")
    for contradiction in context.contradictions:
        lines.append(
            f"- [{contradiction.severity.upper()}] "
            f"{contradiction.contradiction_id}: {contradiction.fact_a} vs {contradiction.fact_b}"
        )
        lines.append(f"  Description: {contradiction.description}")
    return "\n".join(lines)


def _entities(context: VoiceSessionContext) -> str:
    lines = ["KEY ENTITIES:"]
    if not context.entities:
        lines.append("  None identified yet.")
    for entity in context.entities:
        lines.append(
            f"- {entity.name} ({entity.entity_type}): {len(entity.mentions)} mentions"
        )
    return "\n".join(lines)


def _evidence(context: VoiceSessionContext) -> str:
    lines = ["EVIDENCE FILES:"]
    if not context.evidence:
        lines.append("  No evidence uploaded yet.")
    for evidence in context.evidence:
        summary = evidence.summary or "No summary"
        lines.append(
            f"- {evidence.evidence_id}: {evidence.filename} "
            f"({evidence.evidence_type}) - {summary}"
        )
    return "\n".join(lines)


def _report_sections(context: VoiceSessionContext) -> str:
    lines = ["REPORT SECTIONS:"]
    if not context.sections:
        lines.append("  No report generated yet.")
    for section in context.sections:
        label = (section.text or section.title or "(no text)")[:60]
        lines.append(f"- {section.section_id}: [{section.kind}] {label}")
    return "\n".join(lines)


def _instructions() -> str:
    return (
        "You can navigate the user's screen, edit report sections, and pull up "
        "evidence details using your tools. When the user asks about a specific "
        "contradiction or piece of evidence, use navigate_to so they can see it "
        "on screen while you explain."
    )
