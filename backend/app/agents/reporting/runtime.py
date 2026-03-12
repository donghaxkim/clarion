from __future__ import annotations

import inspect
import json
from typing import Any, Awaitable, Callable

from app.agents.reporting.agent_builder import (
    CASE_BUNDLE_STATE,
    COMPOSER_STATE,
    CONTEXT_PLAN_STATE,
    GENERATION_POLICY_STATE,
    MEDIA_PLAN_STATE,
    TIMELINE_PLAN_STATE,
    build_root_agent,
)
from app.agents.reporting.fallback import HeuristicReportingPipeline
from app.agents.reporting.progress import (
    PipelinePreviewSnapshot,
    PipelineProgressEvent,
    ProgressEventBuffer,
)
from app.agents.reporting.types import (
    ComposerOutput,
    ContextPlan,
    MediaPlan,
    PipelineResult,
    ReportGenerationPolicy,
    TimelinePlan,
)
from app.agents.reporting.validators import normalize_composer_output
from app.config import (
    GCS_ALLOW_LOCAL_FALLBACK,
    GCS_BUCKET,
    GOOGLE_API_KEY,
    REPORT_CONTEXT_CACHE_ENABLED,
    REPORT_ENABLE_PUBLIC_CONTEXT,
    REPORT_HELPER_MODEL,
    REPORT_IMAGE_MODEL,
    REPORT_MAX_IMAGES,
    REPORT_MAX_RECONSTRUCTIONS,
    REPORT_SEARCH_MODEL,
    REPORT_TEXT_MODEL,
    VERTEX_PROJECT_ID,
)
from app.models import CaseEvidenceBundle

ProgressCallback = Callable[[PipelineProgressEvent], Awaitable[None] | None]


class AdkReportingPipeline:
    APP_NAME = "clarion_reporting"

    def __init__(self, policy: ReportGenerationPolicy):
        self.policy = policy

    @staticmethod
    def is_available() -> bool:
        try:
            import google.adk  # noqa: F401
            import google.genai  # noqa: F401
        except Exception:
            return False
        return bool(GOOGLE_API_KEY or VERTEX_PROJECT_ID)

    async def run(
        self,
        *,
        bundle: CaseEvidenceBundle,
        report_id: str,
        user_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
        from google.adk.apps import App
        from google.adk.agents.context_cache_config import ContextCacheConfig
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        progress_events = ProgressEventBuffer()
        root_agent = build_root_agent(self.policy, progress_events=progress_events)
        session_service = InMemorySessionService()
        artifact_service = (
            InMemoryArtifactService()
            if GCS_ALLOW_LOCAL_FALLBACK or not GCS_BUCKET
            else GcsArtifactService(bucket_name=GCS_BUCKET)
        )

        app = None
        if self.policy.context_cache_enabled:
            app = App(
                name=self.APP_NAME,
                root_agent=root_agent,
                context_cache_config=ContextCacheConfig(
                    min_tokens=2048,
                    ttl_seconds=600,
                    cache_intervals=5,
                ),
            )

        runner = Runner(
            app=app,
            app_name=None if app is not None else self.APP_NAME,
            agent=None if app is not None else root_agent,
            session_service=session_service,
            artifact_service=artifact_service,
        )

        session_id = f"report-{report_id}"
        await session_service.create_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state=self._initial_state(bundle),
        )

        prompt = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Generate the Clarion report plan from the case bundle in session state. "
                        "Use grounded chronology, optional labeled public context, and output only structured data."
                    )
                )
            ],
        )

        preview_snapshot = PipelinePreviewSnapshot()

        async for _event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=prompt,
        ):
            await _drain_progress_events(progress_events, progress_callback)
            await _emit_snapshot_updates(
                getattr(getattr(_event, "actions", None), "state_delta", {}) or {},
                preview_snapshot=preview_snapshot,
                progress_callback=progress_callback,
            )
            await _drain_progress_events(progress_events, progress_callback)

        await _drain_progress_events(progress_events, progress_callback)

        session = await session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if session is None:
            raise RuntimeError("ADK runner completed without a session result")
        return self._result_from_state(session.state)

    def _initial_state(self, bundle: CaseEvidenceBundle) -> dict[str, Any]:
        return {
            CASE_BUNDLE_STATE: bundle.model_dump(mode="json"),
            GENERATION_POLICY_STATE: self.policy.model_dump(mode="json"),
            CONTEXT_PLAN_STATE: ContextPlan().model_dump(mode="json"),
            MEDIA_PLAN_STATE: MediaPlan().model_dump(mode="json"),
        }

    def _result_from_state(self, state: dict[str, Any]) -> PipelineResult:
        composer = _model_from_state(state, COMPOSER_STATE, ComposerOutput)
        timeline = _model_from_state(state, TIMELINE_PLAN_STATE, TimelinePlan)
        composer = normalize_composer_output(composer, timeline)
        media_plan = _model_from_state(state, MEDIA_PLAN_STATE, MediaPlan)
        return PipelineResult(
            blocks=composer.blocks,
            image_requests=media_plan.image_requests[: self.policy.max_images],
            reconstruction_requests=media_plan.reconstruction_requests[
                : self.policy.max_reconstructions
            ],
            warnings=[],
        )


def build_reporting_pipeline(
    *,
    enable_public_context: bool | None = None,
    max_images: int | None = None,
    max_reconstructions: int | None = None,
) -> AdkReportingPipeline | HeuristicReportingPipeline:
    policy = ReportGenerationPolicy(
        text_model=REPORT_TEXT_MODEL,
        helper_model=REPORT_HELPER_MODEL,
        image_model=REPORT_IMAGE_MODEL,
        search_model=REPORT_SEARCH_MODEL,
        enable_public_context=(
            REPORT_ENABLE_PUBLIC_CONTEXT
            if enable_public_context is None
            else enable_public_context
        ),
        max_images=REPORT_MAX_IMAGES if max_images is None else max_images,
        max_reconstructions=(
            REPORT_MAX_RECONSTRUCTIONS
            if max_reconstructions is None
            else max_reconstructions
        ),
        context_cache_enabled=REPORT_CONTEXT_CACHE_ENABLED,
    )
    if AdkReportingPipeline.is_available():
        return AdkReportingPipeline(policy=policy)
    return HeuristicReportingPipeline(policy=policy)


def _model_from_state(state: dict[str, Any], key: str, model_type: type[Any]) -> Any:
    value = state.get(key)
    if isinstance(value, model_type):
        return value
    if isinstance(value, str):
        try:
            return model_type.model_validate_json(value)
        except Exception:
            return model_type.model_validate(json.loads(value))
    return model_type.model_validate(value or {})


async def _drain_progress_events(
    progress_events: ProgressEventBuffer,
    progress_callback: ProgressCallback | None,
) -> None:
    for event in progress_events.drain():
        await _emit_progress(progress_callback, event)


async def _emit_snapshot_updates(
    state_delta: dict[str, Any],
    *,
    preview_snapshot: PipelinePreviewSnapshot,
    progress_callback: ProgressCallback | None,
) -> None:
    updated = False
    reason = ""

    if TIMELINE_PLAN_STATE in state_delta:
        preview_snapshot.timeline_plan = _model_from_value(
            state_delta[TIMELINE_PLAN_STATE],
            TimelinePlan,
        )
        updated = True
        reason = "timeline_plan"

    if CONTEXT_PLAN_STATE in state_delta:
        preview_snapshot.context_plan = _model_from_value(
            state_delta[CONTEXT_PLAN_STATE],
            ContextPlan,
        )
        updated = True
        reason = "context_plan"

    if MEDIA_PLAN_STATE in state_delta:
        preview_snapshot.media_plan = _model_from_value(
            state_delta[MEDIA_PLAN_STATE],
            MediaPlan,
        )
        updated = True
        reason = "media_plan"

    if COMPOSER_STATE in state_delta:
        preview_snapshot.composer_output = _model_from_value(
            state_delta[COMPOSER_STATE],
            ComposerOutput,
        )
        updated = True
        reason = "composer_output"

    if updated:
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.snapshot_updated(
                preview_snapshot.copy(),
                preview_reason=reason,
            ),
        )


async def _emit_progress(
    progress_callback: ProgressCallback | None,
    event: PipelineProgressEvent,
) -> None:
    if progress_callback is None:
        return
    result = progress_callback(event)
    if inspect.isawaitable(result):
        await result


def _model_from_value(value: Any, model_type: type[Any]) -> Any:
    if isinstance(value, model_type):
        return value
    if isinstance(value, str):
        try:
            return model_type.model_validate_json(value)
        except Exception:
            return model_type.model_validate(json.loads(value))
    return model_type.model_validate(value or {})
