"""
Builds the system instruction for the Gemini Live API voice session.
Takes a CaseFile and produces a text prompt that tells Gemini everything
it needs to know about the case.
"""

from app.models.schema import CaseFile


def build_system_prompt(case: CaseFile) -> str:
    """Build Gemini system instruction from case data."""
    sections = [
        _header(case),
        _contradictions(case),
        _entities(case),
        _evidence(case),
        _report_sections(case),
        _instructions(),
    ]
    return "\n\n".join(sections)


def _header(case: CaseFile) -> str:
    return (
        "You are Clarion, a litigation intelligence assistant. "
        "You speak concisely and professionally, like a sharp paralegal briefing an attorney.\n\n"
        f"CASE: {case.title or 'Untitled Case'}\n"
        f"TYPE: {case.case_type or 'Unknown'}\n"
        f"STATUS: {case.status}"
    )


def _contradictions(case: CaseFile) -> str:
    lines = ["CONTRADICTIONS:"]
    if not case.contradictions:
        lines.append("  None detected yet.")
    for c in case.contradictions:
        sev = c.severity.upper() if isinstance(c.severity, str) else c.severity
        lines.append(f"- [{sev}] {c.id}: {c.fact_a} vs {c.fact_b}")
        lines.append(f"  Description: {c.description}")
    return "\n".join(lines)


def _entities(case: CaseFile) -> str:
    lines = ["KEY ENTITIES:"]
    if not case.entities:
        lines.append("  None identified yet.")
    for e in case.entities:
        lines.append(f"- {e.name} ({e.type}): {len(e.mentions)} mentions")
    return "\n".join(lines)


def _evidence(case: CaseFile) -> str:
    lines = ["EVIDENCE FILES:"]
    if not case.evidence:
        lines.append("  No evidence uploaded yet.")
    for e in case.evidence:
        summary = e.summary or "No summary"
        lines.append(f"- {e.id}: {e.filename} ({e.evidence_type}) — {summary}")
    return "\n".join(lines)


def _report_sections(case: CaseFile) -> str:
    lines = ["REPORT SECTIONS:"]
    if not case.report_sections:
        lines.append("  No report generated yet.")
    for s in case.report_sections:
        label = s.text[:60] if s.text else "(no text)"
        lines.append(f"- {s.id}: [{s.block_type}] {label}")
    return "\n".join(lines)


def _instructions() -> str:
    return (
        "You can navigate the user's screen, edit report sections, and pull up "
        "evidence details using your tools. When the user asks about a specific "
        "contradiction or piece of evidence, use navigate_to so they can see it "
        "on screen while you explain."
    )
