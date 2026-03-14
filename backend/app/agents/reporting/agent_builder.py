from __future__ import annotations

from typing import Any

from app.agents.reporting.callbacks import (
    after_model_guard,
    before_model_guard,
    build_progress_callbacks,
)
from app.agents.reporting.progress import ProgressEventBuffer
from app.agents.reporting.types import (
    ComposerOutput,
    ContextPlan,
    GroundingReview,
    MediaPlan,
    ReportGenerationPolicy,
    TimelinePlan,
)

CASE_BUNDLE_STATE = "case_bundle_json"
GENERATION_POLICY_STATE = "generation_policy_json"
TIMELINE_PLAN_STATE = "timeline_plan_json"
GROUNDING_REVIEW_STATE = "grounding_review_json"
CONTEXT_PLAN_STATE = "context_plan_json"
MEDIA_PLAN_STATE = "media_plan_json"
COMPOSER_STATE = "composer_output_json"


def build_root_agent(
    policy: ReportGenerationPolicy,
    *,
    progress_events: ProgressEventBuffer | None = None,
) -> Any:
    from google.adk.agents import LoopAgent, LlmAgent, SequentialAgent
    from google.adk.agents.parallel_agent import ParallelAgent
    from google.adk.tools.google_search_agent_tool import (
        GoogleSearchAgentTool,
        create_google_search_agent,
    )

    planner_agent = LlmAgent(
        name="TimelinePlannerAgent",
        model=policy.text_model,
        description="Builds a grounded chronological event plan from the case bundle.",
        include_contents="none",
        instruction=_timeline_planner_instruction(),
        output_schema=TimelinePlan,
        output_key=TIMELINE_PLAN_STATE,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events),
    )

    reviewer_agent = LlmAgent(
        name="GroundingReviewerAgent",
        model=policy.text_model,
        description="Checks chronology order and grounding completeness.",
        include_contents="none",
        instruction=_grounding_reviewer_instruction(),
        output_schema=GroundingReview,
        output_key=GROUNDING_REVIEW_STATE,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events),
    )

    refiner_agent = LlmAgent(
        name="TimelineRefinerAgent",
        model=policy.text_model,
        description="Repairs the timeline plan or exits the loop when approved.",
        include_contents="none",
        instruction=_timeline_refiner_instruction(),
        output_schema=TimelinePlan,
        output_key=TIMELINE_PLAN_STATE,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events),
    )

    review_loop = LoopAgent(
        name="GroundingReviewLoop",
        sub_agents=[reviewer_agent, refiner_agent],
        max_iterations=3,
    )

    context_tools = (
        [GoogleSearchAgentTool(create_google_search_agent(policy.search_model))]
        if policy.enable_public_context
        else []
    )
    context_agent = LlmAgent(
        name="ContextEnrichmentAgent",
        model=policy.helper_model,
        description="Creates separately labeled public-context notes when enabled.",
        include_contents="none",
        instruction=_context_enrichment_instruction(policy.enable_public_context),
        output_schema=ContextPlan,
        output_key=CONTEXT_PLAN_STATE,
        tools=context_tools,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events, include_tool_detail=bool(context_tools)),
    )

    media_planner = LlmAgent(
        name="MediaPlannerAgent",
        model=policy.helper_model,
        description="Selects the key events that should receive image or reconstruction media.",
        include_contents="none",
        instruction=_media_planner_instruction(),
        output_schema=MediaPlan,
        output_key=MEDIA_PLAN_STATE,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events),
    )

    enrichment_parallel = ParallelAgent(
        name="ContextAndMediaPlanning",
        sub_agents=[context_agent, media_planner],
        description="Runs optional public-context enrichment and media planning in parallel.",
    )

    composer_agent = LlmAgent(
        name="FinalComposerAgent",
        model=policy.text_model,
        description="Composes the final grounded report blocks from the reviewed timeline and context notes.",
        include_contents="none",
        instruction=_final_composer_instruction(),
        output_schema=ComposerOutput,
        output_key=COMPOSER_STATE,
        before_model_callback=before_model_guard,
        after_model_callback=after_model_guard,
        **build_progress_callbacks(progress_events),
    )

    return SequentialAgent(
        name="ClarionReportingWorkflow",
        sub_agents=[planner_agent, review_loop, enrichment_parallel, composer_agent],
        description="Generates a chronological report with evidence grounding and optional public context.",
    )
def _timeline_planner_instruction() -> str:
    return f"""
You are building the source-of-truth chronology for a legal report.

Input bundle JSON:
{{{CASE_BUNDLE_STATE}}}

Task:
- Produce a strict TimelinePlan JSON object.
- Prefer the provided event_candidates array when present.
- If event_candidates is empty, derive events from evidence_items only.
- Keep events in chronological order using sort_key.
- Every event must include evidence_refs and citations that map to evidence_items.
- Use public_context_queries only as optional later enrichment hints. They are not evidence.
- Keep narratives concise, factual, and courtroom-appropriate.
""".strip()


def _grounding_reviewer_instruction() -> str:
    return f"""
Review the current timeline plan and respond with a GroundingReview JSON object.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Current timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Rules:
- approved must be true only if the timeline is chronologically ordered and every event has evidence_refs and citations.
- issues must explain concrete fixes if approved is false.
- Do not rewrite the timeline in this step.
""".strip()


def _timeline_refiner_instruction() -> str:
    return f"""
You either repair the timeline plan or return it unchanged when it already passes review.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Current timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Review feedback:
{{{GROUNDING_REVIEW_STATE}}}

If the review feedback marks approved=true:
- Return the current TimelinePlan JSON object unchanged.
- Do not add, remove, or reorder events.
Otherwise:
- Return a corrected TimelinePlan JSON object.
- Resolve all listed issues without inventing unsupported evidence.
- Keep sort_key ordering stable wherever possible.
""".strip()


def _context_enrichment_instruction(enable_public_context: bool) -> str:
    if not enable_public_context:
        return "Public context is disabled. Return an empty ContextPlan JSON object."

    return f"""
Create a ContextPlan JSON object with optional public-context notes.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Reviewed timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Rules:
- Only create notes when the timeline event already includes public_context_queries.
 - Use the google_search_agent tool when it helps.
- Keep every note explicitly labeled as public context and separate from evidence.
- Use citations with provenance=public_context only.
- Return an empty notes array if no extra context is necessary.
""".strip()


def _media_planner_instruction() -> str:
    return f"""
Create a MediaPlan JSON object from the reviewed timeline plan.

Current policy:
{{{GENERATION_POLICY_STATE}}}

Reviewed timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Rules:
- Select at most max_images image_requests.
- Select at most max_reconstructions reconstruction_requests.
- Only plan media for the strongest, clearest chronology moments.
- Image requests need prompt text and citations.
- Reconstruction requests need scene_description, evidence_refs, and citations.
- Image requests must use block_type=image.
- Reconstruction requests must use block_type=video.
- block_id values must be unique and anchor_block_id must match the eventual evidence text block id format: event-<event_id>.
""".strip()


def _final_composer_instruction() -> str:
    return f"""
Create a ComposerOutput JSON object for the report.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Reviewed timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Optional context notes:
{{{CONTEXT_PLAN_STATE}}}

Rules:
 - Create one evidence text block per event with id format event-<event_id>.
 - Context notes must become separate text blocks with provenance=public_context and id format context-<index> based on note order.
 - Evidence blocks must use only evidence citations.
 - Public-context blocks must use only public_context citations.
- Blocks must already be sorted by sort_key.
- Do not create image or video blocks here. Media is attached later by the backend.
""".strip()
