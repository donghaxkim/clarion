# Voice Agent Backend Design

## Overview

A real-time voice agent backend for Clarion using the **Gemini Live API** (voice-to-voice). The agent acts as a litigation intelligence assistant that can answer case questions, navigate the UI, and edit report sections. It becomes case-aware once analysis/report data exists.

**Interaction model:** Push-to-talk. User holds the AgentOrb to speak, releases to send.

## Architecture

```
┌─────────────┐     WebSocket (audio + events)     ┌──────────────────┐     WebSocket     ┌─────────────┐
│   Frontend   │ <────────────────────────────────> │  FastAPI Backend  │ <───────────────> │ Gemini Live │
│  (AgentOrb)  │                                    │  (Voice Router)   │                   │     API     │
└─────────────┘                                     └──────────────────┘                    └─────────────┘
      │                                                      │
      │  <- navigation commands (JSON)                       │ <- case context injection
      │  <- edit confirmations                               │ <- tool call interception
      │  -> push-to-talk audio chunks                        │ <- session management
```

Three actors:

1. **Frontend** — captures mic audio on push-to-talk, plays back audio responses, executes navigation/edit commands received from backend.
2. **FastAPI Backend** — new `/ws/voice/{case_id}` WebSocket endpoint. Manages a Gemini Live API session per connection. Injects case context, intercepts tool calls, proxies audio both directions.
3. **Gemini Live API** — receives audio + system instructions + tool definitions, returns audio responses + tool calls.

## Backend Components

New files added to `backend/app/`:

```
backend/app/
├── routers/
│   └── voice.py            # WebSocket endpoint /ws/voice/{case_id}
├── services/
│   └── voice/
│       ├── __init__.py
│       ├── session.py       # GeminiVoiceSession — manages one Gemini Live API connection
│       ├── context.py       # Builds system prompt from case data
│       └── tools.py         # Tool definitions + execution (navigate, edit, query)
```

### voice.py (Router)

The WebSocket endpoint. Accepts a connection, looks up the case, creates a `GeminiVoiceSession`, and runs two concurrent loops:

- **Upstream loop**: reads audio/events from frontend, forwards to Gemini.
- **Downstream loop**: reads audio/tool-calls from Gemini, forwards to frontend.

### session.py (GeminiVoiceSession)

Wraps the Gemini Live API WebSocket. Handles:

- Opening the session with system instructions + tool declarations.
- Sending audio chunks and end-of-turn signals.
- Receiving audio chunks and tool call responses.
- Reconnection if the session drops.

### context.py (Context Builder)

Reads the in-memory case data and builds a system prompt. Re-builds context when case data changes (e.g., after report generation completes).

### tools.py (Tool Definitions)

Defines Gemini function-calling tools and their execution logic:

- `navigate_to(target, id)` — tells frontend to scroll to a contradiction, entity, report section, or evidence item.
- `edit_section(section_id, instruction)` — calls the existing `/api/case/{id}/edit-section` endpoint internally.
- `query_evidence(evidence_id)` — retrieves detailed evidence content to answer specific questions.
- `get_entity_detail(entity_name)` — pulls entity facts and contradictions.

## WebSocket Protocol

### Frontend -> Backend

```json
// Push-to-talk started
{ "type": "audio_start" }

// Audio chunk (while holding)
{ "type": "audio_chunk", "data": "<base64 PCM16 audio>" }

// Push-to-talk released
{ "type": "audio_end" }

// Case context updated (e.g., report just finished generating)
{ "type": "context_update" }
```

### Backend -> Frontend

```json
// Agent speaking — audio chunk
{ "type": "audio_chunk", "data": "<base64 PCM16 audio>" }

// Agent finished speaking
{ "type": "audio_end" }

// Navigation command (from Gemini tool call)
{ "type": "navigate", "target": "contradiction", "id": "c_001" }
{ "type": "navigate", "target": "section", "id": "s_003" }
{ "type": "navigate", "target": "entity", "id": "Michael Chen" }

// Edit result
{ "type": "edit_result", "section_id": "s_003", "status": "success" }

// Agent state changes (for AgentOrb visuals)
{ "type": "state", "value": "listening" }
{ "type": "state", "value": "thinking" }
{ "type": "state", "value": "speaking" }
{ "type": "state", "value": "idle" }

// Error
{ "type": "error", "message": "..." }
```

**Audio format:** 16-bit PCM, 16kHz mono. Base64 encoded over the WebSocket.

## Gemini Live API Integration

### System Instruction

Built by `context.py` when the session opens:

```
You are Clarion, a litigation intelligence assistant. You speak concisely
and professionally, like a sharp paralegal briefing an attorney.

CASE: {case_name}
STATUS: {case_status}

CONTRADICTIONS:
- [HIGH] {fact_a} vs {fact_b} (sources: {src_a}, {src_b})
- ...

KEY ENTITIES:
- {name} ({type}): appeared in {n} documents
- ...

REPORT SECTIONS:
- {section_id}: {title} ({block_type})
- ...

EVIDENCE FILES:
- {evidence_id}: {filename} ({type}, {summary})
- ...

You can navigate the user's screen, edit report sections, and pull up
evidence details using your tools. When the user asks about a specific
contradiction or piece of evidence, use navigate_to so they can see it
on screen while you explain.
```

### Tool Declarations

```python
tools = [
    {
        "name": "navigate_to",
        "description": "Navigate the user's screen to a specific item",
        "parameters": {
            "target": {
                "type": "string",
                "enum": ["contradiction", "entity", "section", "evidence"]
            },
            "id": {
                "type": "string",
                "description": "The ID of the item to navigate to"
            }
        }
    },
    {
        "name": "edit_section",
        "description": "Edit a report section with a natural language instruction",
        "parameters": {
            "section_id": { "type": "string" },
            "instruction": {
                "type": "string",
                "description": "What to change about this section"
            }
        }
    },
    {
        "name": "query_evidence",
        "description": "Get the full parsed content of an evidence file",
        "parameters": {
            "evidence_id": { "type": "string" }
        }
    },
    {
        "name": "get_entity_detail",
        "description": "Get all facts and contradictions for a specific entity",
        "parameters": {
            "entity_name": { "type": "string" }
        }
    }
]
```

### Tool Call Flow

When Gemini makes a tool call, the backend:

1. Executes it (e.g., calls `editSection()` internally, or reads case data).
2. Sends the result back to Gemini so it can incorporate it into its spoken response.
3. Sends the corresponding event to the frontend (e.g., `navigate` command).

## Context Refresh & Session Lifecycle

### When does the agent get case context?

- **On WebSocket connect** — backend loads current case state and builds the system prompt. If the case is still in `intake` or `parsing`, the agent knows limited info and tells the user analysis isn't ready yet.
- **On `context_update` from frontend** — when the report finishes streaming, frontend sends `{ "type": "context_update" }`. Backend rebuilds the system prompt with the full report, contradictions, and entities, then updates the Gemini session.

### Session lifecycle

1. **Connect** — one Gemini Live API session per WebSocket connection. No persistent sessions across page reloads.
2. **Conversation memory** — Gemini Live API maintains conversation history within the session, so the user can reference prior exchanges.
3. **Disconnect** — when the user navigates away or closes the tab, WebSocket closes, backend tears down the Gemini session.
4. **Timeout** — if no audio is sent for 5 minutes, backend sends a keepalive ping. If the Gemini session expires (~15 min idle), backend reconnects transparently and re-injects context.

### Error handling

- Gemini session drops: backend reconnects, re-sends system prompt, sends `{ "type": "state", "value": "idle" }` to frontend.
- Invalid audio format: backend sends `{ "type": "error" }`, doesn't forward to Gemini.
- Case not found: WebSocket closes with 4004 code.

## Dependencies & Configuration

### New Python dependencies

```
google-genai           # Gemini Live API client (supports WebSocket streaming)
```

### Environment variables

```
GEMINI_API_KEY=...     # Already exists — Gemini Live API uses the same key
```

No new infrastructure. The voice backend runs inside the same FastAPI process.

## Frontend Contract (for the frontend agent)

The frontend needs to:

1. Open a WebSocket to `/ws/voice/{case_id}`.
2. Capture mic audio as PCM16/16kHz on push-to-talk.
3. Send/receive the protocol messages defined in the WebSocket Protocol section.
4. Execute `navigate` commands by scrolling/opening the relevant UI element.
5. Update `AgentOrb` state based on `state` messages.
