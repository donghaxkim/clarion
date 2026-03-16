from __future__ import annotations

from typing import Any

from app.agents.reporting.callbacks import (
    after_context_model_guard,
    after_model_guard,
    before_model_guard,
    build_progress_callbacks,
)
from app.agents.reporting.progress import ProgressEventBuffer
from app.agents.reporting.types import (
    CompositionReview,
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
COMPOSITION_REVIEW_STATE = "composition_review_json"
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
        # Loop iterations need prior turn content to avoid empty ADK requests.
        include_contents="default",
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
        include_contents="default",
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
        tools=context_tools,
        before_model_callback=before_model_guard,
        after_model_callback=after_context_model_guard,
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

    composer_reviewer = LlmAgent(
        name="CompositionReviewerAgent",
        model=policy.helper_model,
        description="Checks the drafted report for clipped prose, duplication, and citation mismatches.",
        include_contents="default",
        instruction=_composition_reviewer_instruction(),
        output_schema=CompositionReview,
        output_key=COMPOSITION_REVIEW_STATE,
        before_model_callback=before_model_guard,
        **build_progress_callbacks(progress_events),
    )

    composer_refiner = LlmAgent(
        name="CompositionRefinerAgent",
        model=policy.text_model,
        description="Repairs drafted report prose while preserving ordering, ids, and citations.",
        include_contents="default",
        instruction=_composition_refiner_instruction(),
        output_schema=ComposerOutput,
        output_key=COMPOSER_STATE,
        before_model_callback=before_model_guard,
        after_model_callback=after_model_guard,
        **build_progress_callbacks(progress_events),
    )

    composition_review_loop = LoopAgent(
        name="CompositionReviewLoop",
        sub_agents=[composer_reviewer, composer_refiner],
        max_iterations=2,
    )

    return SequentialAgent(
        name="ClarionReportingWorkflow",
        sub_agents=[
            planner_agent,
            review_loop,
            enrichment_parallel,
            composer_agent,
            composition_review_loop,
        ],
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
- When an event_candidate already includes citations, preserve those citations as the source of truth.
- Evidence citations must stay tied to the relevant evidence_refs. Do not widen a precise citation into a whole-document citation.
- Prefer citations with segment_id and exact excerpt when provided.
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
- Evidence citations must map back to the event's evidence_refs.
- When exact event_candidate citations were provided, they must remain precise and must not be replaced with broader document-level citations.
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
- Preserve precise evidence citations when they already exist on the event candidates.
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
- Produce at most one note per public_context_query, and only when you found grounded public-context content that genuinely helps a reader.
- Keep every note explicitly labeled as public context and separate from evidence.
- Use citations with provenance=public_context only.
- Return exactly one raw JSON object matching this shape:
  {{
    "notes": [
      {{
        "title": "Signal timing context",
        "content": "Public-context note that summarizes the grounded traffic-control context.",
        "sort_key": "0010.005",
        "confidence_score": 0.62,
        "citations": [
          {{
            "source_id": "https://example.com/manual",
            "source_label": "Example Manual",
            "excerpt": "Quoted public-context excerpt supporting the note.",
            "provenance": "public_context",
            "uri": "https://example.com/manual"
          }}
        ]
      }}
    ]
  }}
- Return exactly one raw JSON object matching ContextPlan.
- Do not wrap the JSON in markdown fences or extra prose.
- Do not invent fields such as note_id, topic, summary, confidence, sources, search_results, or results in the final output.
- If you do not have grounded content for a query, omit that note entirely instead of returning placeholders.
- Return {{"notes": []}} if no extra context is necessary.
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
- Prefer zero media over weak, decorative, redundant, or speculative media.
- Only plan media when it clarifies a grounded spatial fact that is not already clear from the real evidence.
- Only plan media for the strongest, clearest chronology moments.
- Image requests are for static spatial clarifications only. Good image subjects include:
  - traffic light or pedestrian-signal state at a key moment
  - pre-impact intersection state
  - static positioning of relevant people
  - room, scene, or hazard layout
  - static body position after an incident
  - object placement relative to people
  - line-of-sight, obstruction, or visibility disputes
- Witness-view scenes should usually be first-person-ish rather than top-down.
- For most other image subjects, prefer diagrammatic or top-down views that emphasize spatial relationships.
- Avoid text baked into the image, labels, captions, marker pins, floor-plan styling, or map styling.
- Keep people and objects generic when appearance details are uncertain. Prioritize spatial relationships over clothing, faces, or exact textures.
- Reconstruction requests are for motion or temporal sequence. Use video for collisions, crashes, movement through space, and action sequences over time.
- Do not create an image for a collision or movement sequence unless the image is a static spatial clarifier such as signal state, viewpoint, line-of-sight, or pre-event positioning.
- Never plan media for:
  - documents on paper, records, transcripts, statements, forms, screenshots, phone/message content
  - generic portraits, stock legal imagery, establishing shots, or generic rooms
  - damage recreation, blurry-evidence cleanup, weather-only scenes, or injury illustrations
  - side-by-side conflicting versions or scenes where the key visual fact is too uncertain
- If a proposed media asset would mostly duplicate a clear real photo or video frame, skip it.
- Do not be overly strict about evidence strength for mock/demo data, but the scene must still be concrete, spatially grounded, and genuinely useful.
- Timeline events may already include visual_scene_spec. Preserve that structured scene spec when you select an event for media.
- The backend will deterministically derive the final media prompt from visual_scene_spec. Your job is to select the right events and keep their grounding intact, not to write a generic final prompt.
- If you do provide prompt or scene_description text, keep it short and factual because the backend may overwrite it with a richer grounded prompt.
- Image requests need citations.
- Reconstruction requests need evidence_refs and citations.
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
- Preserve the event citations from the reviewed timeline plan unless a block is better left uncited than weakly grounded.
- Do not invent broader document-level evidence citations.
- Blocks must already be sorted by sort_key.
- Do not create image or video blocks here. Media is attached later by the backend.
""".strip()


def _composition_reviewer_instruction() -> str:
    return f"""
Review the drafted report blocks and respond with a CompositionReview JSON object.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Reviewed timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Current composer output:
{{{COMPOSER_STATE}}}

Rules:
- approved must be true only if the block text is clear, non-duplicative, and free of clipped/orphaned fragments.
- Flag duplicated or near-duplicated sentence fragments.
- Flag malformed scene prose that reads like raw cue fragments instead of a coherent report sentence.
- Flag any evidence block whose citations do not support the claim being made.
- issues must describe concrete fixes and must not request new evidence.
""".strip()


def _composition_refiner_instruction() -> str:
    return f"""
You either repair the drafted report blocks or return them unchanged when they already pass review.

Current case bundle:
{{{CASE_BUNDLE_STATE}}}

Reviewed timeline plan:
{{{TIMELINE_PLAN_STATE}}}

Current composer output:
{{{COMPOSER_STATE}}}

Composition review feedback:
{{{COMPOSITION_REVIEW_STATE}}}

If the review feedback marks approved=true:
- Return the current ComposerOutput JSON object unchanged.
- Do not add, remove, or reorder blocks.
Otherwise:
- Return a corrected ComposerOutput JSON object.
- Rewrite block text only where needed to fix the listed issues.
- Preserve every block id, sort_key, provenance, and citation unless a citation is better removed than left misleading.
- Do not invent unsupported evidence.
- Keep the report concise, factual, and courtroom-appropriate.
""".strip()
