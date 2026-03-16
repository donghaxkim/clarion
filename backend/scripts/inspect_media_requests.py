#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.reporting.fallback import HeuristicReportingPipeline
from app.agents.reporting.runtime import build_reporting_pipeline
from app.agents.reporting.types import ReportGenerationPolicy
from app.config import (
    REPORT_CONTEXT_CACHE_ENABLED,
    REPORT_ENABLE_PUBLIC_CONTEXT,
    REPORT_HELPER_MODEL,
    REPORT_IMAGE_MODEL,
    REPORT_MAX_IMAGES,
    REPORT_MAX_RECONSTRUCTIONS,
    REPORT_SEARCH_MODEL,
    REPORT_TEXT_MODEL,
)
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    EventCandidate,
    ReportProvenance,
)
from app.models.schema import (
    CaseFile,
    Entity,
    EvidenceItem as LegacyEvidenceItem,
    ExtractedContent,
    MediaRef,
    SourceLocation,
)
from app.services.report_bundle_adapter import build_case_evidence_bundle


def _policy(
    *,
    enable_public_context: bool,
    max_images: int,
    max_reconstructions: int,
) -> ReportGenerationPolicy:
    return ReportGenerationPolicy(
        text_model=REPORT_TEXT_MODEL,
        helper_model=REPORT_HELPER_MODEL,
        image_model=REPORT_IMAGE_MODEL,
        search_model=REPORT_SEARCH_MODEL,
        enable_public_context=enable_public_context,
        max_images=max_images,
        max_reconstructions=max_reconstructions,
        context_cache_enabled=REPORT_CONTEXT_CACHE_ENABLED,
    )


def _simple_bundle() -> CaseEvidenceBundle:
    return CaseEvidenceBundle(
        case_id="case-123",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                kind=EvidenceItemType.transcript,
                title="Witness Transcript",
                summary="Witness describes the signal state before impact.",
            ),
            EvidenceItem(
                evidence_id="ev-2",
                kind=EvidenceItemType.video,
                title="Dashcam Clip",
                summary="Dashcam captures the collision and final rest positions.",
            ),
        ],
        event_candidates=[
            EventCandidate(
                event_id="signal-only",
                title="Traffic signal state before entry",
                description="The signal was yellow when the sedan entered the intersection.",
                sort_key="0001",
                evidence_refs=["ev-1"],
                citations=[
                    Citation(
                        source_id="ev-1",
                        segment_id="ev-1:fact:1",
                        source_label="Witness Transcript",
                        excerpt="The signal was yellow when the sedan entered the intersection.",
                        provenance=ReportProvenance.evidence,
                    )
                ],
                image_prompt_hint="Top-down diagram of the traffic signal state before entry.",
            ),
            EventCandidate(
                event_id="video-only",
                title="Collision sequence",
                description="The pickup turned left across the lane and the sedan struck it.",
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
                scene_description="A neutral collision reconstruction showing the turning movement and impact.",
            ),
        ],
    )


def _pamela_evidence() -> LegacyEvidenceItem:
    evidence = LegacyEvidenceItem(
        id="ev_pamela",
        filename="witness-report-01-pamela-ortiz.pdf",
        evidence_type="witness_statement",
        media=MediaRef(
            url="file:///mock/witness-report-01-pamela-ortiz.pdf",
            media_type="application/pdf",
        ),
        content=ExtractedContent(
            text=(
                "[Page 1]\n"
                "Observation Point: Southeast corner bus stop at E. 14th St. and Brookside Ave., "
                "about 25 feet from the marked crosswalk.\n"
                "I had a clear view of the westbound lanes and nothing was blocking my view.\n"
                "The black pickup had been sitting in the left-turn lane for a few seconds before it started moving.\n"
                "The light for E. 14th looked yellow when the sedan reached the intersection.\n"
                "[Page 2]\n"
                "The pickup started its left turn before the eastbound lane was open.\n"
                "The sedan hit its brakes almost immediately, and the front of the sedan struck the passenger side area of the pickup near the center of the intersection.\n"
                "After the crash, the sedan rolled toward the northeast side and the pickup ended up angled more to the south than west.\n"
                "Statement Time: 10:15 AM.\n"
                "Taken By: Investigator Lauren S. Bell.\n"
                "Witness Signature: /s/ Pamela Ortiz.\n"
            )
        ),
        summary="Pamela Ortiz witnessed the pickup turn left into the path of the sedan at a yellow light.",
        labels=["traffic_accident", "intersection_collision", "left_turn_failure_to_yield"],
        entities=[
            Entity(
                id="ent_pamela",
                type="person",
                name="Pamela Ortiz",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_pamela",
                        page=1,
                        excerpt="Pamela Ortiz",
                    )
                ],
            ),
            Entity(
                id="ent_pickup",
                type="vehicle",
                name="Black pickup",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_pamela",
                        page=1,
                        excerpt="The black pickup had been sitting in the left-turn lane",
                    )
                ],
            ),
        ],
    )
    evidence._analysis = {
        "summary": evidence.summary,
        "labels": list(evidence.labels),
        "key_facts": [
            {
                "fact": "The traffic light was yellow when the sedan reached the intersection.",
                "page": 1,
                "excerpt": "The light for E. 14th looked yellow when the sedan reached the intersection.",
                "category": "incident_description",
            },
            {
                "fact": "The pickup truck turned left across the path of the oncoming sedan.",
                "page": 1,
                "excerpt": "The pickup started its left turn before the eastbound lane was open.",
                "category": "liability",
            },
            {
                "fact": "The front of the sedan struck the passenger side of the pickup truck.",
                "page": 2,
                "excerpt": "the front of the sedan struck the passenger side area of the pickup near the center of the intersection",
                "category": "incident_description",
            },
            {
                "fact": "The witness was positioned approximately 25 feet from the crosswalk with an unobstructed view.",
                "page": 1,
                "excerpt": "about 25 feet from the marked crosswalk... nothing was blocking my view.",
                "category": "witness_account",
            },
        ],
        "timeline_events": [
            {
                "timestamp": "9:18 PM, February 18, 2026",
                "description": "Incident occurs at E. 14th St. and Brookside Ave.",
                "page": 1,
            },
            {
                "timestamp": "10:15 AM, February 19, 2026",
                "description": "Investigator Lauren S. Bell begins recorded in-person interview with Pamela Ortiz.",
                "page": 1,
            },
        ],
    }
    return evidence


def _marcus_evidence() -> LegacyEvidenceItem:
    evidence = LegacyEvidenceItem(
        id="ev_marcus",
        filename="witness-report-02-marcus-reed.pdf",
        evidence_type="witness_statement",
        media=MediaRef(
            url="file:///mock/witness-report-02-marcus-reed.pdf",
            media_type="application/pdf",
        ),
        content=ExtractedContent(
            text=(
                "[Page 1]\n"
                "I came up behind a black pickup that was waiting in the left-turn pocket to go south on Brookside.\n"
                "I also had a direct line of sight to the eastbound sedan coming toward the intersection.\n"
                "The pickup crept forward while the light was still green and then committed to the turn as the signal changed to yellow.\n"
                "The eastbound sedan continued through the yellow without stopping.\n"
                "[Page 2]\n"
                "The sedan braked late and hit the pickup around the passenger-side front door area.\n"
                "The collision happened near the middle of the intersection, maybe slightly east of center.\n"
                "Impact location was near the center of the intersection, with both vehicles ending farther east after contact.\n"
                "Recorded phone interview statement taken by Investigator Lauren S. Bell.\n"
            )
        ),
        summary=(
            "Marcus Reed witnessed the pickup turn left on yellow without a safe gap and the sedan strike it near the center of the intersection."
        ),
        labels=["traffic_accident", "intersection_collision", "yellow_light"],
        entities=[
            Entity(
                id="ent_marcus",
                type="person",
                name="Marcus Reed",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_marcus",
                        page=1,
                        excerpt="Marcus Reed",
                    )
                ],
            )
        ],
    )
    evidence._analysis = {
        "summary": evidence.summary,
        "labels": list(evidence.labels),
        "key_facts": [
            {
                "fact": "The pickup truck turned left across the path of the eastbound sedan as the signal changed to yellow.",
                "page": 1,
                "excerpt": "The pickup crept forward while the light was still green and then committed to the turn as the signal changed to yellow.",
                "category": "liability",
            },
            {
                "fact": "The sedan entered the intersection on a yellow light without stopping.",
                "page": 1,
                "excerpt": "The eastbound sedan continued through the yellow without stopping.",
                "category": "incident_description",
            },
            {
                "fact": "The sedan struck the pickup on the passenger-side front door area.",
                "page": 2,
                "excerpt": "The sedan braked late and hit the pickup around the passenger-side front door area.",
                "category": "incident_description",
            },
            {
                "fact": "The collision occurred near the center of the intersection.",
                "page": 2,
                "excerpt": "The collision happened near the middle of the intersection, maybe slightly east of center.",
                "category": "incident_description",
            },
        ],
        "timeline_events": [
            {
                "timestamp": "9:18 PM, February 18, 2026",
                "description": "Incident occurs at E. 14th St. and Brookside Ave.",
                "page": 1,
            },
            {
                "timestamp": "1:40 PM, February 19, 2026",
                "description": "Recorded phone interview statement taken by Investigator Lauren S. Bell.",
                "page": 1,
            },
        ],
    }
    return evidence


def _derived_case_bundle() -> CaseEvidenceBundle:
    case = CaseFile(
        id="case-123",
        title="Intersection collision",
        intake_summary="Witness statements describing an intersection collision.",
        evidence=[_pamela_evidence(), _marcus_evidence()],
        entities=[
            Entity(id="ent_pamela", type="person", name="Pamela Ortiz"),
            Entity(id="ent_marcus", type="person", name="Marcus Reed"),
        ],
    )
    return build_case_evidence_bundle(case, case_summary=case.intake_summary)


def _serialize_bundle(bundle: CaseEvidenceBundle) -> dict[str, object]:
    return {
        "case_id": bundle.case_id,
        "case_summary": bundle.case_summary,
        "event_candidates": [candidate.model_dump(mode="json") for candidate in bundle.event_candidates],
    }


async def _run(args: argparse.Namespace) -> dict[str, object]:
    bundle = _simple_bundle() if args.fixture == "simple" else _derived_case_bundle()
    enable_public_context = (
        REPORT_ENABLE_PUBLIC_CONTEXT
        if args.enable_public_context is None
        else args.enable_public_context
    )

    if args.pipeline == "fallback":
        pipeline = HeuristicReportingPipeline(
            policy=_policy(
                enable_public_context=enable_public_context,
                max_images=args.max_images,
                max_reconstructions=args.max_reconstructions,
            )
        )
    else:
        pipeline = build_reporting_pipeline(
            enable_public_context=enable_public_context,
            max_images=args.max_images,
            max_reconstructions=args.max_reconstructions,
        )

    result = await pipeline.run(
        bundle=bundle,
        report_id="inspect-report",
        user_id="inspect-user",
    )

    return {
        "fixture": args.fixture,
        "pipeline": pipeline.__class__.__name__,
        "policy": getattr(pipeline, "policy", None).model_dump(mode="json")
        if getattr(pipeline, "policy", None) is not None
        else None,
        "bundle": _serialize_bundle(bundle),
        "image_requests": [request.model_dump(mode="json") for request in result.image_requests],
        "reconstruction_requests": [
            request.model_dump(mode="json") for request in result.reconstruction_requests
        ],
        "warnings": list(result.warnings),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the media requests Clarion would produce for mock evidence."
    )
    parser.add_argument(
        "--fixture",
        choices=("simple", "derived"),
        default="derived",
        help="Which mock evidence fixture to run.",
    )
    parser.add_argument(
        "--pipeline",
        choices=("auto", "fallback"),
        default="fallback",
        help="Use the real auto-selected pipeline or force the deterministic fallback.",
    )
    parser.add_argument(
        "--enable-public-context",
        dest="enable_public_context",
        action="store_true",
        help="Enable public-context enrichment.",
    )
    parser.add_argument(
        "--disable-public-context",
        dest="enable_public_context",
        action="store_false",
        help="Disable public-context enrichment.",
    )
    parser.set_defaults(enable_public_context=None)
    parser.add_argument("--max-images", type=int, default=REPORT_MAX_IMAGES)
    parser.add_argument(
        "--max-reconstructions",
        type=int,
        default=REPORT_MAX_RECONSTRUCTIONS,
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = asyncio.run(_run(args))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
