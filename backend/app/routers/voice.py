"""
WebSocket endpoint for the voice agent.
Bridges frontend audio <-> Gemini Live API with tool call interception.

Reconnection strategy: upstream loop and reconnect watchdog signal reconnects
via an asyncio.Event. The downstream loop watches for this event and re-enters
session.receive() after reconnection completes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types

from app.services.voice.context import build_system_prompt
from app.services.voice.context_service import voice_context_service
from app.services.voice.session import GeminiVoiceSession
from app.services.voice.tools import execute_tool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{report_id}")
async def voice_endpoint(websocket: WebSocket, report_id: str):
    """
    WebSocket endpoint for voice agent communication.
    Proxies audio between the frontend and Gemini Live API.
    """
    await websocket.accept()

    context = voice_context_service.get_context(report_id)
    if context is None:
        await websocket.send_json({"type": "error", "message": "Report not found"})
        await websocket.close(code=4004)
        return

    session = GeminiVoiceSession(build_system_prompt(context))
    reconnected = asyncio.Event()

    try:
        await session.connect()
        await websocket.send_json({"type": "state", "value": "idle"})

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(_upstream_loop(websocket, session, report_id, reconnected))
            task_group.create_task(_downstream_loop(websocket, session, report_id, reconnected))
            task_group.create_task(_reconnect_watchdog(websocket, session, reconnected))

    except* WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected for report %s", report_id)
    except* Exception as exc_group:
        for exc in exc_group.exceptions:
            logger.error("Voice session error for report %s: %s", report_id, exc)
        try:
            await websocket.send_json({"type": "error", "message": "Session error"})
        except Exception:
            pass
    finally:
        await session.close()


async def _upstream_loop(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    report_id: str,
    reconnected: asyncio.Event,
):
    """Read messages from frontend, forward audio to Gemini."""
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
            context = voice_context_service.get_context(report_id)
            if context is None:
                continue
            session.update_system_prompt(build_system_prompt(context))
            await session.reconnect()
            reconnected.set()
            await websocket.send_json({"type": "state", "value": "idle"})


async def _downstream_loop(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    report_id: str,
    reconnected: asyncio.Event,
):
    """Read responses from Gemini, forward audio/events to frontend."""
    while True:
        reconnected.clear()
        speaking = False

        async for response in session.receive():
            if reconnected.is_set():
                break

            server_content = response.server_content
            tool_call = response.tool_call

            if server_content and server_content.model_turn:
                for part in server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        if not speaking:
                            speaking = True
                            await websocket.send_json({"type": "state", "value": "speaking"})
                        audio_b64 = base64.b64encode(part.inline_data.data).decode()
                        await websocket.send_json({"type": "audio_chunk", "data": audio_b64})

            if server_content and server_content.turn_complete and speaking:
                speaking = False
                await websocket.send_json({"type": "audio_end"})
                await websocket.send_json({"type": "state", "value": "idle"})

            if tool_call:
                context = voice_context_service.get_context(report_id)
                if context is None:
                    continue

                function_responses = []
                for function_call in tool_call.function_calls:
                    result_text, frontend_event = execute_tool(
                        function_call.name,
                        dict(function_call.args),
                        context,
                    )
                    if frontend_event:
                        await websocket.send_json(frontend_event)

                    function_responses.append(
                        types.FunctionResponse(
                            name=function_call.name,
                            response={"result": result_text},
                        )
                    )
                await session.send_tool_response(function_responses)

        if not reconnected.is_set():
            logger.warning("Gemini session ended unexpectedly for report %s, reconnecting...", report_id)
            await session.reconnect()
            reconnected.set()

        await asyncio.sleep(0.1)


async def _reconnect_watchdog(
    websocket: WebSocket,
    session: GeminiVoiceSession,
    reconnected: asyncio.Event,
):
    """Proactively reconnect before hitting the 10-minute session limit."""
    while True:
        await asyncio.sleep(30)
        if session.needs_reconnect():
            logger.info("Voice session approaching time limit, reconnecting...")
            await session.reconnect()
            reconnected.set()
            await websocket.send_json({"type": "state", "value": "idle"})
