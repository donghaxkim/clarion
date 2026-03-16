"""
Tool declarations and execution for the Gemini Live API voice session.
Tools let the voice agent navigate the UI, propose report edits, and query
report data.
"""

from google.genai import types

from app.services.voice.models import VoiceSessionContext


def get_tool_declarations() -> types.Tool:
    """Return Gemini function-calling tool declarations."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="navigate_to",
                description="Navigate the user's report page to a section, entity, or evidence item",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "target": types.Schema(
                            type="STRING",
                            enum=["entity", "section", "evidence"],
                        ),
                        "id": types.Schema(
                            type="STRING",
                            description="The section_id, entity_id/name, or evidence_id to navigate to",
                        ),
                    },
                    required=["target", "id"],
                ),
            ),
            types.FunctionDeclaration(
                name="edit_section",
                description="Propose an edit to a specific report section. This only creates a confirmation request and does not persist changes.",
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
                description="Get grounded mentions, facts, and contradictions for a specific entity",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "entity_name": types.Schema(type="STRING"),
                    },
                    required=["entity_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_section_detail",
                description="Get the full text and citations for a report section",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "section_id": types.Schema(type="STRING"),
                    },
                    required=["section_id"],
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
    if name == "get_section_detail":
        return _get_section_detail(args, context)
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
        (
            item
            for item in context.entities
            if item.name.lower() == name.lower()
            or (item.entity_id and item.entity_id == name)
        ),
        None,
    )
    if entity is None:
        return f"Entity '{name}' not found.", None

    parts = [
        f"Entity: {entity.name} ({entity.entity_type})",
        f"Aliases: {', '.join(entity.aliases) if entity.aliases else 'None'}",
        f"Mentions: {len(entity.mentions)}",
    ]

    if entity.mentions:
        parts.append("Mention detail:")
        for mention in entity.mentions[:5]:
            parts.append(
                f"  - {mention.source or mention.evidence_id}: {mention.excerpt or 'Mentioned in this source.'}"
            )

    if entity.facts:
        parts.append(f"Facts: {len(entity.facts)}")
        for fact in entity.facts[:6]:
            parts.append(
                f"  - [{fact.dimension or 'General'}] {fact.fact} "
                f"(Source: {fact.source}; Excerpt: {fact.excerpt})"
            )

    if entity.contradictions:
        parts.append(f"Contradictions: {len(entity.contradictions)}")
        for contradiction in entity.contradictions[:4]:
            parts.append(
                f"  - [{contradiction.severity}] {contradiction.description}"
            )

    return "\n".join(parts), None


def _get_section_detail(args: dict, context: VoiceSessionContext) -> tuple[str, None]:
    section_id = args["section_id"]
    section = next(
        (item for item in context.sections if item.section_id == section_id),
        None,
    )
    if section is None:
        return f"Section '{section_id}' not found.", None

    parts = [
        f"Section: {section.title or section.section_id}",
        f"Kind: {section.kind}",
        f"Text: {section.text or 'No text available.'}",
    ]
    if section.citations:
        parts.append("Citations:")
        for citation in section.citations[:6]:
            parts.append(f"  - {citation.source_label}: {citation.excerpt}")
    return "\n".join(parts), None


def _edit_section(args: dict, context: VoiceSessionContext) -> tuple[str, dict]:
    section_id = args["section_id"]
    instruction = args["instruction"].strip()

    section = next(
        (item for item in context.sections if item.section_id == section_id),
        None,
    )
    if section is None:
        return f"Section {section_id} not found.", {
            "type": "edit_cancelled",
            "section_id": section_id,
            "status": "error",
        }

    summary = _summarize_instruction(instruction)
    event = {
        "type": "edit_proposal",
        "section_id": section.section_id,
        "canonical_block_id": section.canonical_block_id or section.section_id,
        "edit_target": section.edit_target,
        "title": section.title or section.section_id,
        "instruction": instruction,
        "summary": summary,
    }
    return (
        f"Prepared an edit proposal for section {section.section_id}. "
        "Wait for the user to confirm before saying the change is applied.",
        event,
    )


def _summarize_instruction(instruction: str) -> str:
    compact = " ".join(instruction.split())
    if len(compact) <= 120:
        return compact
    return compact[:117].rstrip() + "..."
