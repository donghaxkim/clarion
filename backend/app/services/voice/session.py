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
