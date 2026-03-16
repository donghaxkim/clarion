import asyncio
from types import SimpleNamespace

import pytest

from app.agents.reporting.agent_builder import COMPOSER_STATE, MEDIA_PLAN_STATE, TIMELINE_PLAN_STATE
from app.agents.reporting.callbacks import REPORTING_WARNINGS_STATE
from app.agents.reporting.runtime import AdkReportingPipeline
from app.agents.reporting.types import ComposerOutput, MediaPlan, ReportGenerationPolicy, TimelinePlan
from app.models import CaseEvidenceBundle, EvidenceItem, EvidenceItemType


class _FakeSessionService:
    def __init__(self):
        self._sessions = {}

    async def create_session(self, *, app_name, user_id, session_id, state):
        self._sessions[(app_name, user_id, session_id)] = SimpleNamespace(state=state)

    async def get_session(self, *, app_name, user_id, session_id):
        return self._sessions.get((app_name, user_id, session_id))


class _FakeRunner:
    init_kwargs = None
    warning_state = []

    def __init__(self, **kwargs):
        self.__class__.init_kwargs = kwargs
        self._session_service = kwargs["session_service"]

    async def run_async(self, *, user_id, session_id, new_message):
        del new_message
        session = await self._session_service.get_session(
            app_name=AdkReportingPipeline.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        session.state[TIMELINE_PLAN_STATE] = TimelinePlan().model_dump(mode="json")
        session.state[MEDIA_PLAN_STATE] = MediaPlan().model_dump(mode="json")
        session.state[COMPOSER_STATE] = ComposerOutput().model_dump(mode="json")
        session.state[REPORTING_WARNINGS_STATE] = list(self.__class__.warning_state)
        if False:
            yield None


def test_adk_reporting_runtime_disables_context_cache(monkeypatch):
    pytest.importorskip("google.adk")

    import google.adk.apps as adk_apps
    import google.adk.artifacts as adk_artifacts
    import google.adk.runners as adk_runners
    import google.adk.sessions as adk_sessions

    pipeline = AdkReportingPipeline(
        policy=ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=True,
            context_cache_enabled=True,
        )
    )

    def _forbidden_app(*args, **kwargs):
        raise AssertionError("Reporting runtime should not create an ADK App for caching.")

    monkeypatch.setattr(adk_apps, "App", _forbidden_app)
    monkeypatch.setattr(adk_sessions, "InMemorySessionService", _FakeSessionService)
    monkeypatch.setattr(adk_runners, "Runner", _FakeRunner)
    monkeypatch.setattr(adk_artifacts, "InMemoryArtifactService", lambda: object())
    monkeypatch.setattr(adk_artifacts, "GcsArtifactService", lambda bucket_name: object())
    _FakeRunner.warning_state = []

    result = asyncio.run(
        pipeline.run(
            bundle=CaseEvidenceBundle(
                case_id="case-1",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-1",
                        kind=EvidenceItemType.transcript,
                        summary="Witness described the intersection approach.",
                    )
                ],
            ),
            report_id="report-1",
            user_id="user-1",
        )
    )

    assert _FakeRunner.init_kwargs is not None
    assert _FakeRunner.init_kwargs.get("app_name") == AdkReportingPipeline.APP_NAME
    assert _FakeRunner.init_kwargs.get("agent") is not None
    assert _FakeRunner.init_kwargs.get("app") is None
    assert result.warnings == []


def test_adk_reporting_runtime_returns_reporting_warning_state(monkeypatch):
    pytest.importorskip("google.adk")

    import google.adk.apps as adk_apps
    import google.adk.artifacts as adk_artifacts
    import google.adk.runners as adk_runners
    import google.adk.sessions as adk_sessions

    pipeline = AdkReportingPipeline(
        policy=ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=True,
            context_cache_enabled=True,
        )
    )

    monkeypatch.setattr(adk_apps, "App", lambda *args, **kwargs: None)
    monkeypatch.setattr(adk_sessions, "InMemorySessionService", _FakeSessionService)
    monkeypatch.setattr(adk_runners, "Runner", _FakeRunner)
    monkeypatch.setattr(adk_artifacts, "InMemoryArtifactService", lambda: object())
    monkeypatch.setattr(adk_artifacts, "GcsArtifactService", lambda bucket_name: object())
    _FakeRunner.warning_state = [
        "Public-context enrichment omitted: invalid ContextPlan payload. Output preview: not valid json at all"
    ]

    result = asyncio.run(
        pipeline.run(
            bundle=CaseEvidenceBundle(
                case_id="case-1",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-1",
                        kind=EvidenceItemType.transcript,
                        summary="Witness described the intersection approach.",
                    )
                ],
            ),
            report_id="report-1",
            user_id="user-1",
        )
    )

    assert result.warnings == _FakeRunner.warning_state
