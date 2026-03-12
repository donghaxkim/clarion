"""
WebSocket endpoint for the voice agent.
Bridges frontend audio <-> Gemini Live API with tool call interception.

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
