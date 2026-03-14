"""
Tool declarations and execution for the Gemini Live API voice session.
Tools let the voice agent navigate the UI, edit reports, and query case data.
"""

from google.genai import types
from app.models.schema import CaseFile


def get_tool_declarations() -> types.Tool:
    """Return Gemini function-calling tool declarations."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="navigate_to",
                description="Navigate the user's screen to a specific item",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "target": types.Schema(
                            type="STRING",
                            enum=["contradiction", "entity", "section", "evidence"],
                        ),
                        "id": types.Schema(
                            type="STRING",
                            description="The ID of the item to navigate to",
                        ),
                    },
                    required=["target", "id"],
                ),
            ),
            types.FunctionDeclaration(
                name="edit_section",
                description="Edit a report section with a natural language instruction",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "section_id": types.Schema(type="STRING"),
                        "instruction": types.Schema(
                            type="STRING",
                            description="What to change about this section",
                        ),
                    },
                    required=["section_id", "instruction"],
                ),
            ),
            types.FunctionDeclaration(
                name="query_evidence",
                description="Get the full parsed content of an evidence file (truncated to 2000 chars)",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "evidence_id": types.Schema(type="STRING"),
                    },
                    required=["evidence_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_entity_detail",
                description="Get all facts and contradictions for a specific entity",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "entity_name": types.Schema(type="STRING"),
                    },
                    required=["entity_name"],
                ),
            ),
        ]
    )


def execute_tool(
    name: str,
    args: dict,
    case: CaseFile,
) -> tuple[str, dict | None]:
    """
    Execute a tool call and return (result_text, frontend_event).
    result_text goes back to Gemini. frontend_event goes to the frontend (or None).
    """
    if name == "navigate_to":
        return _navigate_to(args)
    elif name == "query_evidence":
        return _query_evidence(args, case)
    elif name == "get_entity_detail":
        return _get_entity_detail(args, case)
    elif name == "edit_section":
        return _edit_section(args, case)
    else:
        return f"Unknown tool: {name}", None


def _navigate_to(args: dict) -> tuple[str, dict]:
    target = args["target"]
    item_id = args["id"]
    event = {"type": "navigate", "target": target, "id": item_id}
    return f"Navigated to {target} {item_id}.", event


def _query_evidence(args: dict, case: CaseFile) -> tuple[str, None]:
    eid = args["evidence_id"]
    evidence = next((e for e in case.evidence if e.id == eid), None)
    if not evidence:
        return f"Evidence {eid} not found.", None

    text = evidence.content.text or ""
    if len(text) > 2000:
        text = text[:2000] + "... (truncated)"

    parts = [
        f"Evidence: {evidence.filename} ({evidence.evidence_type})",
        f"Summary: {evidence.summary or 'None'}",
        f"Content: {text}",
    ]
    return "\n".join(parts), None


def _get_entity_detail(args: dict, case: CaseFile) -> tuple[str, None]:
    name = args["entity_name"]
    entity = next(
        (e for e in case.entities if e.name.lower() == name.lower()),
        None,
    )
    if not entity:
        return f"Entity '{name}' not found.", None

    parts = [
        f"Entity: {entity.name} ({entity.type})",
        f"Aliases: {', '.join(entity.aliases) if entity.aliases else 'None'}",
        f"Mentions: {len(entity.mentions)} across evidence",
    ]

    # Find contradictions involving this entity by searching fact text and description
    related = [
        c for c in case.contradictions
        if name.lower() in c.description.lower()
        or name.lower() in c.fact_a.lower()
        or name.lower() in c.fact_b.lower()
    ]
    if related:
        parts.append(f"Contradictions: {len(related)}")
        for c in related:
            parts.append(f"  - [{c.severity}] {c.description}")

    return "\n".join(parts), None


def _edit_section(args: dict, case: CaseFile) -> tuple[str, dict]:
    section_id = args["section_id"]
    instruction = args["instruction"]

    section = next((s for s in case.report_sections if s.id == section_id), None)
    if not section:
        return f"Section {section_id} not found.", {
            "type": "edit_result", "section_id": section_id, "status": "error"
        }

    event = {"type": "edit_result", "section_id": section_id, "status": "success"}
    return f"Edit request submitted for section {section_id}: '{instruction}'", event
