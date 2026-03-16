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
        _focused_section(context),
        _missing_info(context),
        _contradictions(context),
        _entities(context),
        _evidence(context),
        _report_sections(context),
        _instructions(context),
    ]
    return "\n\n".join(section for section in sections if section.strip())


def _header(context: VoiceSessionContext) -> str:
    mode = "section-focused" if context.focused_section is not None else "report-wide"
    return (
        "You are Clarion, a litigation intelligence voice assistant. "
        "Speak concisely, clearly, and professionally, like a sharp paralegal "
        "briefing trial counsel.\n\n"
        f"MODE: {mode}\n"
        f"CASE: {context.title or 'Untitled Case'}\n"
        f"TYPE: {context.case_type or 'Unknown'}\n"
        f"REPORT STATUS: {context.status}"
    )


def _focused_section(context: VoiceSessionContext) -> str:
    if context.focused_section is None:
        return "FOCUSED SECTION:\n  None. The user is asking about the report as a whole."

    section = context.focused_section
    lines = [
        "FOCUSED SECTION:",
        f"- SECTION ID: {section.section_id}",
        f"- BLOCK TYPE: {section.kind}",
        f"- TITLE: {section.title or 'Untitled section'}",
        f"- TEXT: {section.text or 'No text available.'}",
    ]
    if section.citations:
        lines.append("- CITATIONS:")
        for citation in section.citations[:4]:
            lines.append(f"  * {citation.source_label}: {citation.excerpt}")
    return "\n".join(lines)


def _missing_info(context: VoiceSessionContext) -> str:
    lines = ["EVIDENCE GAPS:"]
    if not context.missing_info:
        lines.append("  None identified.")
    for item in context.missing_info:
        lines.append(
            f"- [{item.severity.upper()}] {item.description} "
            f"(Recommendation: {item.recommendation})"
        )
    return "\n".join(lines)


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
            f"- {entity.name} ({entity.entity_type}) | "
            f"mentions={len(entity.mentions)} facts={len(entity.facts)} contradictions={len(entity.contradictions)}"
        )
        for fact in entity.facts[:2]:
            lines.append(
                f"  Fact: {fact.fact} | Source: {fact.source} | Excerpt: {fact.excerpt}"
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
        lines.append(
            f"- {section.section_id}: [{section.kind}] {section.title or 'Untitled'}"
        )
        if section.text:
            lines.append(f"  Text: {section.text}")
        if section.citations:
            for citation in section.citations[:3]:
                lines.append(f"  Citation: {citation.source_label} -> {citation.excerpt}")
    return "\n".join(lines)


def _instructions(context: VoiceSessionContext) -> str:
    focus_note = (
        "Prioritize the focused section unless the user explicitly asks about a different part of the report."
        if context.focused_section is not None
        else "Answer at the report level unless the user names a specific section."
    )
    return (
        "INSTRUCTIONS:\n"
        "- Ground your answers in the report text, citations, evidence summaries, entity facts, contradictions, and evidence gaps.\n"
        f"- {focus_note}\n"
        "- If the user asks what the opposition could argue, separate evidence-grounded weaknesses from your own adversarial reasoning.\n"
        "- Use get_section_detail for full section text when you need more detail.\n"
        "- Use get_entity_detail for grounded entity facts, mentions, and contradictions.\n"
        "- Use query_evidence for source text before making factual claims about a file.\n"
        "- Use navigate_to only for section, entity, or evidence targets the report page can actually show.\n"
        "- Use edit_section only when the user clearly wants to change report content. Edits require explicit user confirmation before they are applied.\n"
        "- Never claim an edit is already saved until the user confirms and you receive the follow-up context."
    )
