"""
Tool declarations and execution for the Gemini Live API voice session.
Tools let the voice agent navigate the UI, edit reports, and query report data.
"""

from google.genai import types

from app.services.voice.models import VoiceSessionContext


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
    context: VoiceSessionContext,
) -> tuple[str, dict | None]:
    """
    Execute a tool call and return (result_text, frontend_event).
    result_text goes back to Gemini. frontend_event goes to the frontend (or None).
    """
    if name == "navigate_to":
        return _navigate_to(args)
    if name == "query_evidence":
        return _query_evidence(args, context)
    if name == "get_entity_detail":
        return _get_entity_detail(args, context)
    if name == "edit_section":
        return _edit_section(args, context)
    return f"Unknown tool: {name}", None


def _navigate_to(args: dict) -> tuple[str, dict]:
    target = args["target"]
    item_id = args["id"]
    event = {"type": "navigate", "target": target, "id": item_id}
    return f"Navigated to {target} {item_id}.", event


def _query_evidence(args: dict, context: VoiceSessionContext) -> tuple[str, None]:
    evidence_id = args["evidence_id"]
    evidence = next(
        (item for item in context.evidence if item.evidence_id == evidence_id),
        None,
    )
    if evidence is None:
        return f"Evidence {evidence_id} not found.", None

    text = evidence.content_text or ""
    if len(text) > 2000:
        text = text[:2000] + "... (truncated)"

    parts = [
        f"Evidence: {evidence.filename} ({evidence.evidence_type})",
        f"Summary: {evidence.summary or 'None'}",
        f"Content: {text}",
    ]
    return "\n".join(parts), None


def _get_entity_detail(args: dict, context: VoiceSessionContext) -> tuple[str, None]:
    name = args["entity_name"]
    entity = next(
        (item for item in context.entities if item.name.lower() == name.lower()),
        None,
    )
    if entity is None:
        return f"Entity '{name}' not found.", None

    parts = [
        f"Entity: {entity.name} ({entity.entity_type})",
        f"Aliases: {', '.join(entity.aliases) if entity.aliases else 'None'}",
        f"Mentions: {len(entity.mentions)} across evidence",
    ]

    related = [
        contradiction
        for contradiction in context.contradictions
        if name.lower() in contradiction.description.lower()
        or name.lower() in (contradiction.fact_a or "").lower()
        or name.lower() in (contradiction.fact_b or "").lower()
    ]
    if related:
        parts.append(f"Contradictions: {len(related)}")
        for contradiction in related:
            parts.append(
                f"  - [{contradiction.severity}] {contradiction.description}"
            )

    return "\n".join(parts), None


def _edit_section(args: dict, context: VoiceSessionContext) -> tuple[str, dict]:
    section_id = args["section_id"]
    instruction = args["instruction"]

    section = next(
        (item for item in context.sections if item.section_id == section_id),
        None,
    )
    if section is None:
        return f"Section {section_id} not found.", {
            "type": "edit_result",
            "section_id": section_id,
            "status": "error",
        }

    event = {"type": "edit_result", "section_id": section_id, "status": "success"}
    return f"Edit request submitted for section {section_id}: '{instruction}'", event
