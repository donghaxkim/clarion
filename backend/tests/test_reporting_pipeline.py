import asyncio

import pytest

from app.agents.reporting.agent_builder import build_root_agent
from app.agents.reporting.fallback import HeuristicReportingPipeline
from app.agents.reporting.types import ReportGenerationPolicy
from app.models import (
    CaseEvidenceBundle,
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
                image_prompt_hint="Sedan approaching an intersection",
                public_context_queries=["intersection sight-distance standards"],
            ),
            EventCandidate(
                event_id="event-2",
                title="Collision",
                description="The dashcam captures the collision sequence.",
                sort_key="0002",
                evidence_refs=["ev-2"],
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
        citation.provenance == ReportProvenance.public_context
        for block in result.blocks
        if block.provenance == ReportProvenance.public_context
        for citation in block.citations
    )


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
    assert result.warnings


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
