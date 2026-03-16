import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import voice
from app.services.voice.models import VoiceReportSection, VoiceSessionContext


class _DummyContextService:
    def __init__(self, context):
        self._context = context
        self.requests = []

    def get_context(self, report_id: str, *, focused_section_id: str | None = None):
        self.requests.append((report_id, focused_section_id))
        return self._context


class _FakeSession:
    next_responses = []
    instances = []

    def __init__(self, prompt: str):
        self.prompt = prompt
        self.closed = False
        self.tool_responses = []
        self.text_turns = []
        self._responses = list(type(self).next_responses)
        type(self).instances.append(self)

    async def connect(self):
        return None

    async def send_audio(self, audio_bytes: bytes):
        del audio_bytes
        return None

    async def send_end_of_turn(self):
        return None

    async def send_text_turn(self, text: str):
        self.text_turns.append(text)

    async def send_tool_response(self, function_responses):
        self.tool_responses.append(function_responses)

    async def receive(self):
        while not self.closed:
            if self._responses:
                yield self._responses.pop(0)
                continue
            await asyncio.sleep(0.01)

    def needs_reconnect(self) -> bool:
        return False

    def update_system_prompt(self, new_prompt: str):
        self.prompt = new_prompt

    async def reconnect(self):
        return None

    async def close(self):
        self.closed = True


def _make_context() -> VoiceSessionContext:
    return VoiceSessionContext(
        report_id="report-1",
        case_id="case-1",
        title="Smith v. Johnson",
        case_type="personal_injury",
        status="completed",
        sections=[
            VoiceReportSection(
                section_id="section-1",
                canonical_block_id="section-1",
                kind="text",
                edit_target="content",
                title="Collision Summary",
                text="Vehicle A struck Vehicle B from behind.",
            )
        ],
    )


def test_voice_websocket_returns_error_for_unknown_report(monkeypatch):
    monkeypatch.setattr(voice, "voice_context_service", _DummyContextService(None))

    with TestClient(app) as client:
        with client.websocket_connect("/voice/ws/missing-report") as websocket:
            payload = websocket.receive_json()
            assert payload == {"type": "error", "message": "Report not found"}


def test_voice_websocket_uses_report_context_and_emits_tool_event(monkeypatch):
    _FakeSession.instances.clear()
    _FakeSession.next_responses = [
        SimpleNamespace(
            server_content=None,
            tool_call=SimpleNamespace(
                function_calls=[
                    SimpleNamespace(
                        name="navigate_to",
                        args={"target": "section", "id": "section-1"},
                    )
                ]
            ),
        )
    ]

    context_service = _DummyContextService(_make_context())
    monkeypatch.setattr(voice, "voice_context_service", context_service)
    monkeypatch.setattr(voice, "GeminiVoiceSession", _FakeSession)

    with TestClient(app) as client:
        with client.websocket_connect("/voice/ws/report-1") as websocket:
            state = websocket.receive_json()
            assert state == {"type": "state", "value": "idle"}

            navigate = websocket.receive_json()
            assert navigate == {
                "type": "navigate",
                "target": "section",
                "id": "section-1",
            }
            websocket.close()

    assert _FakeSession.instances
    assert len(_FakeSession.instances[0].tool_responses) == 1
    assert context_service.requests[0] == ("report-1", None)


def test_voice_websocket_accepts_context_updates_and_text_turns(monkeypatch):
    _FakeSession.instances.clear()
    _FakeSession.next_responses = []
    context_service = _DummyContextService(_make_context())
    monkeypatch.setattr(voice, "voice_context_service", context_service)
    monkeypatch.setattr(voice, "GeminiVoiceSession", _FakeSession)

    with TestClient(app) as client:
        with client.websocket_connect("/voice/ws/report-1") as websocket:
            websocket.receive_json()

            websocket.send_json(
                {"type": "context_update", "focused_section_id": "section-1"}
            )
            state = websocket.receive_json()
            assert state == {"type": "state", "value": "idle"}

            websocket.send_json(
                {
                    "type": "text_turn",
                    "text": "The user confirmed the proposed change.",
                }
            )
            thinking = websocket.receive_json()
            assert thinking == {"type": "state", "value": "thinking"}
            websocket.close()

    assert context_service.requests[-1] == ("report-1", "section-1")
    assert _FakeSession.instances[0].text_turns == [
        "The user confirmed the proposed change."
    ]
