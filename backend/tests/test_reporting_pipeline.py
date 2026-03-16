import asyncio

import pytest

from app.agents.reporting.agent_builder import build_root_agent
from app.agents.reporting.fallback import HeuristicReportingPipeline
from app.agents.reporting.types import (
    MediaPlan,
    MediaRequest,
    ComposerOutput,
    ComposedBlockDraft,
    ReportGenerationPolicy,
    TimelineEvent,
    TimelinePlan,
)
from app.agents.reporting.validators import normalize_composer_output, normalize_media_plan
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    EventCandidate,
    ReportBlockType,
    ReportProvenance,
    VisualSceneActor,
    VisualSceneMotionBeat,
    VisualSceneSpec,
    VisualSceneStyle,
)
from app.services.generation.media_prompting import PROMPT_SOURCE_SCENE_SPEC


def _signal_scene_spec() -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_key="signal-state",
        visual_goal="show the signal state and vehicle placement before entry",
        style=VisualSceneStyle.top_down_diagram,
        camera_framing="top-down view of the intersection approaches",
        actors=[
            VisualSceneActor(
                actor_id="pickup",
                label="black pickup truck",
                kind="pickup truck",
                color="black",
                travel_direction="westbound",
                lane_position="left-turn lane",
                evidence_refs=["ev-1"],
            ),
            VisualSceneActor(
                actor_id="sedan",
                label="sedan",
                kind="sedan",
                travel_direction="eastbound",
                lane_position="through lane",
                evidence_refs=["ev-1"],
            ),
        ],
        traffic_control_details=["traffic signal showing yellow at vehicle entry"],
        grounded_facts=["pickup waiting in the left-turn lane before turning"],
        interpolated_details=["simple lane geometry with neutral roadway markings only where needed for orientation"],
    )


def _collision_scene_spec() -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_key="collision-sequence",
        visual_goal="show approach, turn, braking response, impact, and short post-impact motion",
        style=VisualSceneStyle.grounded_motion,
        camera_framing="steady elevated three-quarter view of the intersection",
        actors=[
            VisualSceneActor(
                actor_id="pickup",
                label="black pickup truck",
                kind="pickup truck",
                color="black",
                lane_position="left-turn lane",
                action="turning left across opposing traffic",
                evidence_refs=["ev-2"],
            ),
            VisualSceneActor(
                actor_id="sedan",
                label="sedan",
                kind="sedan",
                travel_direction="eastbound",
                action="braking immediately before impact",
                evidence_refs=["ev-2"],
            ),
        ],
        traffic_control_details=["traffic signal showing yellow at vehicle entry"],
        grounded_facts=["front of the sedan strikes the passenger side of the pickup near the center of the intersection"],
        motion_beats=[
            VisualSceneMotionBeat(
                order=1,
                description="pickup waits in the left-turn lane while the sedan approaches",
                evidence_refs=["ev-2"],
            ),
            VisualSceneMotionBeat(
                order=2,
                description="pickup turns left across the opposing lane and the sedan brakes before impact",
                evidence_refs=["ev-2"],
            ),
        ],
        interpolated_details=["single steady camera and simplified lane geometry only where needed for orientation"],
    )


def _bundle(with_candidates: bool = True) -> CaseEvidenceBundle:
    evidence_items = [
        EvidenceItem(
            evidence_id="ev-1",
            kind=EvidenceItemType.transcript,
            title="Witness Transcript",
            summary="Witness states the sedan entered the intersection first.",
        ),
        EvidenceItem(
            evidence_id="ev-2",
            kind=EvidenceItemType.video,
            title="Dashcam Clip",
            summary="Dashcam captures the collision and final rest positions.",
        ),
    ]
    event_candidates = []
    if with_candidates:
        event_candidates = [
            EventCandidate(
                event_id="event-1",
                title="Approach to Intersection",
                description="The sedan approaches the intersection before impact.",
                sort_key="0001",
                evidence_refs=["ev-1"],
                citations=[
                    Citation(
                        source_id="ev-1",
                        segment_id="ev-1:fact:1",
                        source_label="Witness Transcript",
                        excerpt="The sedan approached the intersection before impact.",
                        provenance=ReportProvenance.evidence,
                    )
                ],
                image_prompt_hint=(
                    "Top-down diagram of the traffic light state before the vehicles "
                    "entered the intersection."
                ),
                visual_scene_spec=_signal_scene_spec(),
                public_context_queries=["intersection sight-distance standards"],
            ),
            EventCandidate(
                event_id="event-2",
                title="Collision",
                description="The dashcam captures the collision sequence.",
                sort_key="0002",
                evidence_refs=["ev-2"],
                citations=[
                    Citation(
                        source_id="ev-2",
                        segment_id="ev-2:fact:1",
                        source_label="Dashcam Clip",
                        excerpt="Dashcam captures the collision and final rest positions.",
                        provenance=ReportProvenance.evidence,
                    )
                ],
                scene_description="A two-car collision viewed from a dashboard camera.",
                visual_scene_spec=_collision_scene_spec(),
            ),
        ]
    return CaseEvidenceBundle(
        case_id="case-123",
        evidence_items=evidence_items,
        event_candidates=event_candidates,
    )


def test_fallback_pipeline_uses_event_candidates_without_placeholder_public_context():
    pipeline = HeuristicReportingPipeline(
        policy=ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=True,
            max_images=1,
            max_reconstructions=1,
        )
    )

    result = asyncio.run(pipeline.run(bundle=_bundle(), report_id="report-1", user_id="user-1"))

    assert all(block.type == ReportBlockType.text for block in result.blocks)
    assert all(block.id != "timeline-overview" for block in result.blocks)
    assert result.blocks[0].id == "event-event-1"
    assert all(block.provenance != ReportProvenance.public_context for block in result.blocks)
    assert len(result.image_requests) == 1
    assert len(result.reconstruction_requests) == 1
    assert result.image_requests[0].block_type == ReportBlockType.image
    assert result.reconstruction_requests[0].block_type == ReportBlockType.video
    assert result.image_requests[0].prompt_source == PROMPT_SOURCE_SCENE_SPEC
    assert result.reconstruction_requests[0].prompt_source == PROMPT_SOURCE_SCENE_SPEC
    assert result.reconstruction_requests[0].negative_prompt
    assert all(
        citation.source_label and citation.excerpt
        for block in result.blocks
        for citation in block.citations
    )
    assert result.blocks[0].citations[0].segment_id == "ev-1:fact:1"
    assert result.reconstruction_requests[0].citations[0].segment_id == "ev-2:fact:1"


def test_fallback_pipeline_only_generates_media_from_explicit_candidate_fields():
    bundle = CaseEvidenceBundle(
        case_id="case-123",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                kind=EvidenceItemType.transcript,
                title="Witness Transcript",
                summary="Witness describes the signal state before impact.",
            )
        ],
        event_candidates=[
            EventCandidate(
                event_id="signal-only",
                title="Traffic signal state before entry",
                description="The signal was yellow when the sedan entered the intersection.",
                sort_key="0001",
                evidence_refs=["ev-1"],
                image_prompt_hint="Top-down diagram of the traffic signal state before entry.",
                visual_scene_spec=_signal_scene_spec(),
            ),
            EventCandidate(
                event_id="video-only",
                title="Collision sequence",
                description="The pickup turned left across the lane and the sedan struck it.",
                sort_key="0002",
                evidence_refs=["ev-1"],
                scene_description="A neutral collision reconstruction showing the turning movement and impact.",
                visual_scene_spec=_collision_scene_spec(),
            ),
        ],
    )
    pipeline = HeuristicReportingPipeline(
        policy=ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=False,
            max_images=2,
            max_reconstructions=2,
        )
    )

    result = asyncio.run(pipeline.run(bundle=bundle, report_id="report-3", user_id="user-1"))

    assert [request.block_id for request in result.image_requests] == ["event-signal-only-image"]
    assert [request.block_id for request in result.reconstruction_requests] == [
        "event-video-only-video"
    ]
    assert result.image_requests[0].prompt_source == PROMPT_SOURCE_SCENE_SPEC
    assert result.reconstruction_requests[0].negative_prompt


def test_fallback_pipeline_derives_timeline_when_event_candidates_missing():
    pipeline = HeuristicReportingPipeline(
        policy=ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=False,
            max_images=2,
            max_reconstructions=2,
        )
    )

    result = asyncio.run(
        pipeline.run(
            bundle=_bundle(with_candidates=False),
            report_id="report-2",
            user_id="user-1",
        )
    )

    event_blocks = [block for block in result.blocks if block.id.startswith("event-derived")]
    assert len(event_blocks) == 2
    assert all(
        citation.source_label and citation.excerpt
        for block in event_blocks
        for citation in block.citations
    )
    assert result.image_requests == []
    assert result.reconstruction_requests == []
    assert result.warnings


def test_normalize_media_plan_filters_banned_images_and_keeps_spatial_clarifiers():
    timeline = TimelinePlan(
        timeline_events=[
            TimelineEvent(
                event_id="signal",
                title="Traffic light state",
                narrative="The witness describes the traffic light state before entry.",
                sort_key="0001",
                evidence_refs=["ev-1"],
                citations=[Citation(source_id="ev-1")],
                image_prompt="Top-down diagram of the traffic light state before the collision.",
                visual_scene_spec=_signal_scene_spec(),
            ),
            TimelineEvent(
                event_id="impact",
                title="Collision sequence",
                narrative="The vehicles collide in the intersection.",
                sort_key="0002",
                evidence_refs=["ev-2"],
                citations=[Citation(source_id="ev-2")],
                scene_description="A two-car collision sequence through the intersection.",
                visual_scene_spec=_collision_scene_spec(),
            ),
        ]
    )
    media_plan = MediaPlan(
        image_requests=[
            MediaRequest(
                block_id="event-signal-image",
                block_type=ReportBlockType.image,
                anchor_block_id="event-signal",
                title="Signal state",
                sort_key="0001.10",
                citations=[Citation(source_id="ev-1")],
                prompt="Top-down diagram of the traffic light state before the collision.",
            ),
            MediaRequest(
                block_id="event-doc-image",
                block_type=ReportBlockType.image,
                anchor_block_id="event-signal",
                title="Witness statement photo",
                sort_key="0001.11",
                citations=[Citation(source_id="ev-1")],
                prompt="Photo of the witness statement on a piece of paper.",
            ),
            MediaRequest(
                block_id="event-impact-image",
                block_type=ReportBlockType.image,
                anchor_block_id="event-impact",
                title="Crash still",
                sort_key="0002.10",
                citations=[Citation(source_id="ev-2")],
                prompt="Sedan approaching the intersection before impact.",
            ),
        ],
        reconstruction_requests=[
            MediaRequest(
                block_id="event-impact-video",
                block_type=ReportBlockType.video,
                anchor_block_id="event-impact",
                title="Collision reconstruction",
                sort_key="0002.20",
                citations=[Citation(source_id="ev-2")],
                scene_description="A two-car collision sequence through the intersection.",
                evidence_refs=["ev-2"],
            ),
            MediaRequest(
                block_id="event-doc-video",
                block_type=ReportBlockType.video,
                anchor_block_id="event-signal",
                title="Document recreation",
                sort_key="0001.20",
                citations=[Citation(source_id="ev-1")],
                scene_description="A close-up of a police report document on paper.",
                evidence_refs=["ev-1"],
            ),
        ],
    )

    normalized = normalize_media_plan(media_plan, timeline)

    assert [request.block_id for request in normalized.image_requests] == ["event-signal-image"]
    assert [request.block_id for request in normalized.reconstruction_requests] == [
        "event-impact-video"
    ]
    assert normalized.image_requests[0].prompt_source == PROMPT_SOURCE_SCENE_SPEC
    assert "black pickup truck" in normalized.image_requests[0].prompt.lower()
    assert normalized.reconstruction_requests[0].negative_prompt


def test_adk_context_agent_wraps_google_search_for_public_context():
    pytest.importorskip("google.adk")

    root_agent = build_root_agent(
        ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=True,
        )
    )

    context_agent = root_agent.sub_agents[2].sub_agents[0]
    search_tool = context_agent.tools[0]

    assert search_tool.__class__.__name__ == "GoogleSearchAgentTool"
    assert getattr(search_tool.agent, "model", None) == "gemini-2.5-flash"
    # The old ADK failure was:
    # "Failed to parse the parameter notes: list[...ContextNote] of function
    # set_model_response". Keep the context agent off that automatic schema path.
    assert getattr(context_agent, "output_schema", None) is None
    assert getattr(context_agent, "output_key", None) is None
    assert getattr(context_agent, "after_model_callback", None) is not None


def test_adk_refiner_agent_avoids_tool_plus_output_schema_combo():
    pytest.importorskip("google.adk")

    root_agent = build_root_agent(
        ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=False,
        )
    )

    refiner_agent = root_agent.sub_agents[1].sub_agents[1]

    assert getattr(refiner_agent, "tools", []) == []


def test_adk_loop_agents_keep_contents_for_repeat_iterations():
    pytest.importorskip("google.adk")

    root_agent = build_root_agent(
        ReportGenerationPolicy(
            text_model="gemini-3-pro-preview",
            helper_model="gemini-3-flash-preview",
            image_model="gemini-3-pro-image-preview",
            search_model="gemini-2.5-flash",
            enable_public_context=True,
        )
    )

    grounding_reviewer = root_agent.sub_agents[1].sub_agents[0]
    grounding_refiner = root_agent.sub_agents[1].sub_agents[1]
    composition_reviewer = root_agent.sub_agents[4].sub_agents[0]
    composition_refiner = root_agent.sub_agents[4].sub_agents[1]

    assert grounding_reviewer.include_contents == "default"
    assert grounding_refiner.include_contents == "default"
    assert composition_reviewer.include_contents == "default"
    assert composition_refiner.include_contents == "default"


def test_normalize_composer_output_strips_media_blocks_and_dedupes_text_ids():
    timeline = TimelinePlan(
        timeline_events=[
            TimelineEvent(
                event_id="impact",
                title="Impact",
                narrative="Vehicles collide in the intersection.",
                sort_key="0001",
                evidence_refs=["ev-1"],
                citations=[
                    Citation(
                        source_id="ev-1",
                        segment_id="ev-1:fact:1",
                        source_label="Witness Transcript",
                        excerpt="The vehicles collided in the intersection.",
                        provenance=ReportProvenance.evidence,
                    )
                ],
            )
        ]
    )
    output = ComposerOutput(
        blocks=[
            ComposedBlockDraft(
                id="event-impact",
                type=ReportBlockType.text,
                title="Impact",
                content="Earlier impact draft.",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                confidence_score=0.7,
            ),
            ComposedBlockDraft(
                id="image-impact",
                type=ReportBlockType.image,
                title="Impact still",
                content=None,
                sort_key="0001.10",
                provenance=ReportProvenance.evidence,
                confidence_score=0.7,
            ),
            ComposedBlockDraft(
                id="context-alpha",
                type=ReportBlockType.text,
                title="Bad context id",
                content="Should be dropped.",
                sort_key="0001.15",
                provenance=ReportProvenance.public_context,
                confidence_score=0.5,
            ),
            ComposedBlockDraft(
                id="event-impact",
                type=ReportBlockType.text,
                title="Impact",
                content="Final impact draft.",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                confidence_score=0.9,
            ),
            ComposedBlockDraft(
                id="context-1",
                type=ReportBlockType.text,
                title="Public context",
                content="Grounded context note.",
                sort_key="0001.50",
                provenance=ReportProvenance.public_context,
                confidence_score=0.6,
            ),
            ComposedBlockDraft(
                id="video-impact",
                type=ReportBlockType.video,
                title="Impact video",
                content=None,
                sort_key="0001.20",
                provenance=ReportProvenance.evidence,
                confidence_score=0.7,
            ),
        ]
    )

    normalized = normalize_composer_output(output, timeline)

    assert [block.id for block in normalized.blocks] == ["event-impact", "context-1"]
    assert all(block.type == ReportBlockType.text for block in normalized.blocks)
    assert normalized.blocks[0].content == "Final impact draft."
    assert normalized.blocks[0].citations[0].segment_id == "ev-1:fact:1"
