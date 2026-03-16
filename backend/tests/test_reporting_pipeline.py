import asyncio

import pytest

from app.agents.reporting.agent_builder import build_root_agent
from app.agents.reporting.fallback import HeuristicReportingPipeline
from app.agents.reporting.types import (
    MediaPlan,
    MediaRequest,
    ReportGenerationPolicy,
    TimelineEvent,
    TimelinePlan,
)
from app.agents.reporting.validators import normalize_media_plan
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    EventCandidate,
    ReportBlockType,
    ReportProvenance,
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
            ),
        ]
    return CaseEvidenceBundle(
        case_id="case-123",
        evidence_items=evidence_items,
        event_candidates=event_candidates,
    )


def test_fallback_pipeline_uses_event_candidates_and_separates_public_context():
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
    assert any(block.provenance == ReportProvenance.public_context for block in result.blocks)
    assert len(result.image_requests) == 1
    assert len(result.reconstruction_requests) == 1
    assert result.image_requests[0].block_type == ReportBlockType.image
    assert result.reconstruction_requests[0].block_type == ReportBlockType.video
    assert all(
        citation.source_label and citation.excerpt
        for block in result.blocks
        for citation in block.citations
    )
    assert all(
        citation.provenance == ReportProvenance.public_context
        for block in result.blocks
        if block.provenance == ReportProvenance.public_context
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
            ),
            EventCandidate(
                event_id="video-only",
                title="Collision sequence",
                description="The pickup turned left across the lane and the sedan struck it.",
                sort_key="0002",
                evidence_refs=["ev-1"],
                scene_description="A neutral collision reconstruction showing the turning movement and impact.",
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
            ),
            TimelineEvent(
                event_id="impact",
                title="Collision sequence",
                narrative="The vehicles collide in the intersection.",
                sort_key="0002",
                evidence_refs=["ev-2"],
                citations=[Citation(source_id="ev-2")],
                scene_description="A two-car collision sequence through the intersection.",
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
