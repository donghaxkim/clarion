# Voice Agent Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time voice agent backend that proxies audio between the frontend and Gemini Live API, with case-aware context injection and tool calling for navigation, editing, and querying.

**Architecture:** FastAPI WebSocket endpoint (`/ws/voice/{case_id}`) acts as a smart proxy between frontend and Gemini Live API. Backend injects case context as system instructions, defines tools for navigation/editing/querying, intercepts tool calls and forwards structured events to the frontend. Push-to-talk model — no VAD needed.

**Tech Stack:** Python 3.13, FastAPI, google-genai (already installed), asyncio

**Spec:** `docs/superpowers/specs/2026-03-11-voice-agent-backend-design.md`

---

## File Structure

```
backend/app/
├── main.py                          # MODIFY: register voice router
├── services/
│   └── voice/
│       ├── __init__.py              # CREATE: package init
│       ├── session.py               # CREATE: GeminiVoiceSession wrapper
│       ├── context.py               # CREATE: case context → system prompt builder
│       └── tools.py                 # CREATE: tool declarations + executor
├── routers/
│   └── voice.py                     # CREATE: WebSocket endpoint
```

**Responsibilities:**
- `session.py` — Owns the Gemini Live API WebSocket connection. Send audio, receive audio/tool-calls, handle reconnection.
- `context.py` — Pure function: takes a `CaseFile` + `CitationIndex` → returns a system instruction string.
- `tools.py` — Defines tool schemas for Gemini, executes tool calls against case data, returns results.
- `routers/voice.py` — WebSocket endpoint. Bridges frontend WS ↔ GeminiVoiceSession. Runs upstream/downstream loops.

---

## Chunk 1: Core Voice Infrastructure

### Task 1: Context Builder (`context.py`)

No external dependencies. Pure data transformation.

**Files:**
- Create: `backend/app/services/voice/__init__.py`
- Create: `backend/app/services/voice/context.py`
- Test: `backend/tests/test_context.py`

- [ ] **Step 1: Create the voice services package**

```python
# backend/app/services/voice/__init__.py
```

Empty init file.

- [ ] **Step 2: Write test for context builder**

```python
# backend/tests/test_context.py
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
    assert "CONTRADICTIONS" in prompt  # section header still present
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion && python -m pytest backend/tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.voice'`

- [ ] **Step 4: Implement context builder**

```python
# backend/app/services/voice/context.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion && python -m pytest backend/tests/test_context.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/voice/__init__.py backend/app/services/voice/context.py backend/tests/test_context.py
git commit -m "feat(voice): add context builder for Gemini system prompt"
```

---

### Task 2: Tool Declarations & Executor (`tools.py`)

Depends on: Task 1 (for package init). Needs access to `cases` dict and `citation_indices` from `main.py`.

**Files:**
- Create: `backend/app/services/voice/tools.py`
- Test: `backend/tests/test_voice_tools.py`

- [ ] **Step 1: Write tests for tool declarations and executor**

```python
# backend/tests/test_voice_tools.py
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
    assert frontend_event is None  # no frontend event for queries


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion && python -m pytest backend/tests/test_voice_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools.py**

```python
# backend/app/services/voice/tools.py
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

    # For now, mark as pending edit. The actual regeneration calls the existing
    # edit-section logic which is a placeholder (Larris's domain).
    event = {"type": "edit_result", "section_id": section_id, "status": "success"}
    return f"Edit request submitted for section {section_id}: '{instruction}'", event
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion && python -m pytest backend/tests/test_voice_tools.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voice/tools.py backend/tests/test_voice_tools.py
git commit -m "feat(voice): add tool declarations and executor for Gemini function calling"
```

---

### Task 3: Gemini Voice Session (`session.py`)

The core wrapper around the Gemini Live API WebSocket. This is the most complex component.

**Files:**
- Create: `backend/app/services/voice/session.py`

- [ ] **Step 1: Implement GeminiVoiceSession**

```python
# backend/app/services/voice/session.py
"""
Manages a single Gemini Live API WebSocket session.
Handles connection, audio streaming, tool call responses, and reconnection.
"""

import asyncio
import base64
import time
import logging

from google import genai
from google.genai import types

from app.services.voice.tools import get_tool_declarations
from app.utils.gemini_client import get_client

logger = logging.getLogger(__name__)

LIVE_MODEL = "gemini-2.0-flash-live-001"
SESSION_MAX_SECONDS = 540  # reconnect at 9 min (hard limit ~10 min)


class GeminiVoiceSession:
    """
    Wraps one Gemini Live API async session.

    Usage:
        session = GeminiVoiceSession(system_prompt)
        await session.connect()
        await session.send_audio(chunk_bytes)
        await session.send_end_of_turn()
        # reads come via async iteration in the downstream loop
        await session.close()
    """

    def __init__(self, system_prompt: str):
        self._system_prompt = system_prompt
        self._client = get_client()
        self._session = None
        self._connected = False
        self._connect_time: float = 0

    async def connect(self):
        """Open the Gemini Live API session."""
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=self._system_prompt)]
            ),
            tools=[get_tool_declarations()],
        )
        self._session = await self._client.aio.live.connect(
            model=LIVE_MODEL,
            config=config,
        )
        self._connected = True
        self._connect_time = time.monotonic()
        logger.info("Gemini Live session connected")

    async def send_audio(self, audio_bytes: bytes):
        """Send a chunk of PCM16 audio to Gemini."""
        if not self._session:
            return
        await self._session.send_realtime_input(
            audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
        )

    async def send_end_of_turn(self):
        """Signal that the user has finished speaking."""
        if not self._session:
            return
        await self._session.send_client_content(turns=None, turn_complete=True)

    async def send_tool_response(self, function_responses: list[types.FunctionResponse]):
        """Send tool execution results back to Gemini."""
        if not self._session:
            return
        await self._session.send_tool_response(function_responses=function_responses)

    async def receive(self):
        """
        Async generator that yields responses from Gemini.
        Each response may contain audio data, tool calls, or text.
        """
        if not self._session:
            return
        async for response in self._session.receive():
            yield response

    def needs_reconnect(self) -> bool:
        """Check if we're approaching the session time limit."""
        if not self._connected:
            return False
        elapsed = time.monotonic() - self._connect_time
        return elapsed >= SESSION_MAX_SECONDS

    def update_system_prompt(self, new_prompt: str):
        """Update the system prompt for the next reconnect."""
        self._system_prompt = new_prompt

    async def close(self):
        """Close the Gemini session."""
        self._connected = False
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
        logger.info("Gemini Live session closed")

    async def reconnect(self):
        """Tear down and reconnect with the same system prompt."""
        await self.close()
        await self.connect()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/voice/session.py
git commit -m "feat(voice): add GeminiVoiceSession wrapper for Live API"
```

---

### Task 4: WebSocket Router (`routers/voice.py`)

Bridges the frontend WebSocket and the Gemini session. Runs upstream/downstream loops concurrently.

**Files:**
- Create: `backend/app/routers/voice.py`
- Modify: `backend/app/main.py` (register the router)

- [ ] **Step 1: Implement the voice WebSocket router**

```python
# backend/app/routers/voice.py
"""
WebSocket endpoint for the voice agent.
Bridges frontend audio ↔ Gemini Live API with tool call interception.

Reconnection strategy: upstream loop and reconnect watchdog signal reconnects
via an asyncio.Event. The downstream loop watches for this event and re-enters
session.receive() after reconnection completes.
"""

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from google.genai import types

from app.services.voice.session import GeminiVoiceSession
from app.services.voice.context import build_system_prompt
from app.services.voice.tools import execute_tool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/voice/{case_id}")
async def voice_endpoint(websocket: WebSocket, case_id: str):
    """
    WebSocket endpoint for voice agent communication.
    Proxies audio between the frontend and Gemini Live API.
    """
    from app.main import cases

    await websocket.accept()

    if case_id not in cases:
        await websocket.send_json({"type": "error", "message": "Case not found"})
        await websocket.close(code=4004)
        return

    case = cases[case_id]
    system_prompt = build_system_prompt(case)
    session = GeminiVoiceSession(system_prompt)

    # Event set when a reconnect happens — downstream loop watches this
    reconnected = asyncio.Event()

    try:
        await session.connect()
        await websocket.send_json({"type": "state", "value": "idle"})

        async with asyncio.TaskGroup() as tg:
            tg.create_task(_upstream_loop(websocket, session, case_id, reconnected))
            tg.create_task(_downstream_loop(websocket, session, case_id, reconnected))
            tg.create_task(_reconnect_watchdog(websocket, session, reconnected))

    except* WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected for case {case_id}")
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.error(f"Voice session error: {exc}")
        try:
            await websocket.send_json({"type": "error", "message": "Session error"})
        except Exception:
            pass
    finally:
        await session.close()


async def _upstream_loop(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    case_id: str,
    reconnected: asyncio.Event,
):
    """Read messages from frontend, forward audio to Gemini."""
    from app.main import cases

    while True:
        raw = await websocket.receive_text()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio_start":
            await websocket.send_json({"type": "state", "value": "listening"})

        elif msg_type == "audio_chunk":
            audio_bytes = base64.b64decode(msg["data"])
            await session.send_audio(audio_bytes)

        elif msg_type == "audio_end":
            await websocket.send_json({"type": "state", "value": "thinking"})
            await session.send_end_of_turn()

        elif msg_type == "context_update":
            if case_id in cases:
                case = cases[case_id]
                new_prompt = build_system_prompt(case)
                session.update_system_prompt(new_prompt)
                await session.reconnect()
                reconnected.set()
                await websocket.send_json({"type": "state", "value": "idle"})


async def _downstream_loop(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    case_id: str,
    reconnected: asyncio.Event,
):
    """Read responses from Gemini, forward audio/events to frontend.

    Re-enters session.receive() whenever a reconnect event fires.
    """
    from app.main import cases

    while True:
        reconnected.clear()
        speaking = False

        async for response in session.receive():
            # Check if a reconnect happened — break out to re-enter receive()
            if reconnected.is_set():
                break

            server_content = response.server_content
            tool_call = response.tool_call

            # Handle audio response
            if server_content and server_content.model_turn:
                for part in server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        if not speaking:
                            speaking = True
                            await websocket.send_json({"type": "state", "value": "speaking"})
                        audio_b64 = base64.b64encode(part.inline_data.data).decode()
                        await websocket.send_json({"type": "audio_chunk", "data": audio_b64})

            # Handle turn complete
            if server_content and server_content.turn_complete:
                if speaking:
                    speaking = False
                    await websocket.send_json({"type": "audio_end"})
                    await websocket.send_json({"type": "state", "value": "idle"})

            # Handle tool calls
            if tool_call:
                function_responses = []
                case = cases.get(case_id)
                if not case:
                    continue

                for fc in tool_call.function_calls:
                    result_text, frontend_event = execute_tool(
                        fc.name, dict(fc.args), case
                    )
                    if frontend_event:
                        await websocket.send_json(frontend_event)

                    function_responses.append(
                        types.FunctionResponse(
                            name=fc.name,
                            response={"result": result_text},
                        )
                    )
                await session.send_tool_response(function_responses)

        # If receive() ended without a reconnect event, session died unexpectedly
        if not reconnected.is_set():
            logger.warning("Gemini session ended unexpectedly, reconnecting...")
            await session.reconnect()
            reconnected.set()

        # Small delay before re-entering receive loop
        await asyncio.sleep(0.1)


async def _reconnect_watchdog(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    reconnected: asyncio.Event,
):
    """Proactively reconnect before hitting the 10-min session limit."""
    while True:
        await asyncio.sleep(30)
        if session.needs_reconnect():
            logger.info("Session approaching time limit, reconnecting...")
            await session.reconnect()
            reconnected.set()
            await websocket.send_json({"type": "state", "value": "idle"})
```

- [ ] **Step 2: Register the voice router in main.py**

Add to `backend/app/main.py` after the existing imports (around line 33):

```python
from app.routers.voice import router as voice_router
```

Add after the CORS middleware setup (around line 51):

```python
app.include_router(voice_router)
```

- [ ] **Step 3: Verify the server starts without errors**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion/backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/voice.py backend/app/main.py
git commit -m "feat(voice): add WebSocket router and wire up to FastAPI app"
```

---

## Chunk 2: Integration & Testing

### Task 5: Create test directory and run all tests

**Files:**
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create tests package init**

```python
# backend/tests/__init__.py
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion && python -m pytest backend/tests/ -v`
Expected: All tests PASS (context + tools tests)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/__init__.py
git commit -m "test(voice): add test package init and verify all tests pass"
```

---

### Task 6: Manual Integration Test

- [ ] **Step 1: Start the backend server**

Run: `cd /Users/gimdongha/Desktop/Projects/clarion/backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000`

- [ ] **Step 2: Test WebSocket connection with a Python script**

Create and run a quick test:

```python
# backend/tests/manual_ws_test.py (temporary, do not commit)
"""Quick manual test — run while uvicorn is running."""
import asyncio
import json
import websockets

async def test():
    # First create a case via HTTP
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8000/api/case/create", data={"title": "Test Case"})
        case_id = resp.json()["case_id"]
        print(f"Created case: {case_id}")

    # Connect to voice WebSocket
    uri = f"ws://localhost:8000/ws/voice/{case_id}"
    async with websockets.connect(uri) as ws:
        # Should receive idle state
        msg = await ws.recv()
        data = json.loads(msg)
        print(f"Received: {data}")
        assert data == {"type": "state", "value": "idle"}, f"Expected idle, got {data}"
        print("WebSocket connection test PASSED")

asyncio.run(test())
```

Run: `cd /Users/gimdongha/Desktop/Projects/clarion/backend && source venv/bin/activate && python tests/manual_ws_test.py`
Expected: "WebSocket connection test PASSED"

Note: This requires `GOOGLE_API_KEY` to be set in `.env` for the Gemini session to connect. If the key is not set, the test will fail at the Gemini connection step — the WebSocket accept and case validation will still work.

- [ ] **Step 3: Clean up manual test file**

Delete `backend/tests/manual_ws_test.py` — it was just for manual verification.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(voice): complete voice agent backend with Gemini Live API integration"
```
