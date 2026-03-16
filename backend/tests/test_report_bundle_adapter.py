from app.models.schema import CaseFile, Entity, EvidenceItem, ExtractedContent, MediaRef, SourceLocation
from app.services.report_bundle_adapter import build_case_evidence_bundle


def _make_pamela_evidence() -> EvidenceItem:
    evidence = EvidenceItem(
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
                "excerpt": "The light for E. 14th looked yellow when the sedan reached the intersection",
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
            {
                "timestamp": "February 19, 2026",
                "description": "Pamela Ortiz signs the witness statement.",
                "page": 2,
            },
        ],
    }
    return evidence


def _make_marcus_evidence() -> EvidenceItem:
    evidence = EvidenceItem(
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
                "Statement signed and attested by Marcus Reed.\n"
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
                "excerpt": "The pickup crept forward while the light was still green and then actually committed to the turn as the signal changed to yellow.",
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
            {
                "timestamp": "February 19, 2026",
                "description": "Statement signed and attested by Marcus Reed.",
                "page": 2,
            },
        ],
    }
    return evidence


def test_build_case_evidence_bundle_enriches_evidence_and_curates_scene_candidates():
    case = CaseFile(
        id="case-123",
        title="Intersection collision",
        intake_summary="Witness statements describing an intersection collision.",
        evidence=[_make_pamela_evidence(), _make_marcus_evidence()],
        entities=[
            Entity(id="ent_pamela", type="person", name="Pamela Ortiz"),
            Entity(id="ent_marcus", type="person", name="Marcus Reed"),
        ],
    )

    bundle = build_case_evidence_bundle(case, case_summary=case.intake_summary)

    assert len(bundle.evidence_items) == 2
    assert bundle.evidence_items[0].source_spans
    assert bundle.evidence_items[0].metadata["labels"]
    assert bundle.evidence_items[0].metadata["key_facts"]
    assert bundle.evidence_items[0].metadata["entity_names"]
    assert bundle.evidence_items[0].metadata["chronology_hints"]
    assert "timeline_events" not in bundle.evidence_items[0].metadata

    candidate_lookup = {candidate.event_id: candidate for candidate in bundle.event_candidates}
    assert "collision_sequence" in candidate_lookup
    assert "signal_state" in candidate_lookup
    assert "witness_viewpoint" in candidate_lookup
    assert candidate_lookup["collision_sequence"].scene_description
    assert candidate_lookup["collision_sequence"].image_prompt_hint is None
    assert candidate_lookup["signal_state"].image_prompt_hint
    assert candidate_lookup["signal_state"].scene_description is None
    assert set(candidate_lookup["collision_sequence"].evidence_refs) == {"ev_pamela", "ev_marcus"}
    assert candidate_lookup["signal_state"].timestamp_label == "9:18 PM, February 18, 2026"
    assert candidate_lookup["collision_sequence"].citations
    assert all(citation.segment_id for citation in candidate_lookup["collision_sequence"].citations)
    assert all(citation.source_label for citation in candidate_lookup["collision_sequence"].citations)
    assert all(citation.excerpt for citation in candidate_lookup["collision_sequence"].citations)

    lowered_titles = [candidate.title.lower() for candidate in bundle.event_candidates]
    lowered_descriptions = [candidate.description.lower() for candidate in bundle.event_candidates]
    assert not any("interview" in title for title in lowered_titles)
    assert not any("statement signed" in description for description in lowered_descriptions)
    assert not any("attested" in description for description in lowered_descriptions)
    assert any("line of sight" in candidate.title.lower() for candidate in bundle.event_candidates)


def test_scene_candidates_create_deterministic_fragment_spans_when_only_raw_text_is_available():
    evidence = EvidenceItem(
        id="ev_fragment",
        filename="intersection-note.txt",
        evidence_type="witness_statement",
        media=MediaRef(
            url="file:///mock/intersection-note.txt",
            media_type="text/plain",
        ),
        content=ExtractedContent(
            text=(
                "[Page 1]\n"
                "The black pickup was waiting in the left-turn lane before moving into the intersection.\n"
                "The eastbound sedan struck the passenger side of the pickup near the center of the intersection.\n"
            )
        ),
        summary="Witness notes the pickup waiting to turn before the impact.",
        labels=["traffic_accident"],
        entities=[],
    )

    case = CaseFile(
        id="case-fragment",
        title="Intersection note",
        evidence=[evidence],
        entities=[],
    )

    bundle = build_case_evidence_bundle(case)

    collision = next(candidate for candidate in bundle.event_candidates if candidate.event_id == "collision_sequence")
    assert collision.citations
    assert collision.citations[0].segment_id.startswith("ev_fragment:scene:")
    assert collision.citations[0].excerpt == (
        "The eastbound sedan struck the passenger side of the pickup near the center of the intersection."
    )
    stored_spans = {
        span.segment_id: span.snippet
        for span in bundle.evidence_items[0].source_spans
    }
    assert collision.citations[0].segment_id in stored_spans
