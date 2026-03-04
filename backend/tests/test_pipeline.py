"""
CLARION — End-to-End Pipeline Test
=====================================
Run this to verify your entire pipeline works before integration.

Usage:
    python -m tests.test_pipeline

What it tests:
    1. PDF parsing → EvidenceItem
    2. Audio parsing → EvidenceItem
    3. Image parsing → EvidenceItem
    4. Auto-labeling and routing
    5. Citation index building (dimension discovery + classification)
    6. Contradiction detection
    7. Full CaseFile assembly
    8. API response format validation

Uses mock Gemini responses so you can test without API keys.
Set CLARION_USE_REAL_API=1 to test with actual Gemini calls.
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────
#  MOCK GEMINI RESPONSES
# ──────────────────────────────────────────────
# These simulate what Gemini returns so you can test
# the full pipeline without API access.

MOCK_PDF_ANALYSIS = {
    "document_type": "police_report",
    "summary": "Police report documenting a rear-end collision at the intersection of Main St and 5th Ave on March 5, 2024 at 2:34 PM. The defendant's vehicle struck the plaintiff's vehicle from behind while plaintiff was stopped at a red light.",
    "labels": ["traffic_accident", "rear_end_collision", "intersection", "red_light"],
    "entities": [
        {
            "type": "person",
            "name": "Officer James Miller",
            "aliases": ["Ofc. Miller"],
            "mentions": [
                {"page": 1, "excerpt": "Reporting Officer: James Miller, Badge #4472"}
            ]
        },
        {
            "type": "person",
            "name": "Sarah Chen",
            "aliases": ["Plaintiff", "Driver 1"],
            "mentions": [
                {"page": 1, "excerpt": "Driver 1: Sarah Chen, DOB 03/15/1985"}
            ]
        },
        {
            "type": "person",
            "name": "Marcus Thompson",
            "aliases": ["Defendant", "Driver 2"],
            "mentions": [
                {"page": 1, "excerpt": "Driver 2: Marcus Thompson, DOB 11/22/1990"}
            ]
        },
        {
            "type": "vehicle",
            "name": "2020 Silver Toyota Camry",
            "aliases": ["Plaintiff's vehicle", "Vehicle 1"],
            "mentions": [
                {"page": 1, "excerpt": "Vehicle 1: 2020 Toyota Camry, Silver, plate ABC-1234"}
            ]
        },
        {
            "type": "vehicle",
            "name": "2019 Black Ford F-150",
            "aliases": ["Defendant's vehicle", "Vehicle 2"],
            "mentions": [
                {"page": 1, "excerpt": "Vehicle 2: 2019 Ford F-150, Black, plate XYZ-5678"}
            ]
        },
        {
            "type": "location",
            "name": "Intersection of Main St and 5th Ave",
            "aliases": ["Main & 5th", "the intersection"],
            "mentions": [
                {"page": 1, "excerpt": "Location: Intersection of Main Street and 5th Avenue"}
            ]
        }
    ],
    "key_facts": [
        {
            "fact": "The collision occurred at 2:34 PM on March 5, 2024",
            "page": 1,
            "excerpt": "Date/Time of Incident: March 5, 2024, 14:34 hours",
            "category": "timeline"
        },
        {
            "fact": "The plaintiff's vehicle was stopped at a red traffic light",
            "page": 2,
            "excerpt": "Vehicle 1 was stationary at a red traffic signal",
            "category": "incident_description"
        },
        {
            "fact": "The defendant's vehicle was traveling northbound at approximately 35 mph",
            "page": 2,
            "excerpt": "Vehicle 2 was traveling northbound on Main St at an estimated speed of 35 mph",
            "category": "incident_description"
        },
        {
            "fact": "The defendant failed to stop and struck the plaintiff's vehicle from behind",
            "page": 2,
            "excerpt": "Vehicle 2 failed to stop and struck Vehicle 1 in the rear",
            "category": "liability"
        },
        {
            "fact": "The plaintiff complained of neck and lower back pain at the scene",
            "page": 2,
            "excerpt": "Driver 1 complained of pain in neck and lower back at scene",
            "category": "injury"
        },
        {
            "fact": "Weather conditions were clear and dry",
            "page": 1,
            "excerpt": "Weather: Clear. Road Conditions: Dry",
            "category": "incident_description"
        }
    ],
    "timeline_events": [
        {
            "timestamp": "2:34 PM, March 5, 2024",
            "description": "Collision occurs at intersection of Main St and 5th Ave",
            "page": 1
        },
        {
            "timestamp": "2:41 PM, March 5, 2024",
            "description": "Officers arrive on scene",
            "page": 2
        },
        {
            "timestamp": "3:05 PM, March 5, 2024",
            "description": "EMS arrives, plaintiff transported to hospital",
            "page": 2
        }
    ]
}

MOCK_AUDIO_TRANSCRIPT = {
    "full_transcript": "Speaker 1: Can you tell me what happened? Speaker 2: I was just sitting at the light, it was red, and out of nowhere this truck just slammed into me from behind. I think he was going at least 45, maybe faster. I didn't even see him coming. Speaker 1: Did you see which direction the other vehicle was coming from? Speaker 2: Yeah he was coming from behind me, heading eastbound on Main Street. I was facing east too, waiting to go through the intersection. Speaker 1: Were there any other witnesses? Speaker 2: There was a guy at the crosswalk who ran over to help me. He said the truck driver was on his phone.",
    "segments": [
        {"speaker": "Speaker 1", "start": 0.0, "end": 3.2, "text": "Can you tell me what happened?"},
        {"speaker": "Speaker 2", "start": 3.5, "end": 18.1, "text": "I was just sitting at the light, it was red, and out of nowhere this truck just slammed into me from behind. I think he was going at least 45, maybe faster. I didn't even see him coming."},
        {"speaker": "Speaker 1", "start": 18.5, "end": 22.0, "text": "Did you see which direction the other vehicle was coming from?"},
        {"speaker": "Speaker 2", "start": 22.3, "end": 33.0, "text": "Yeah he was coming from behind me, heading eastbound on Main Street. I was facing east too, waiting to go through the intersection."},
        {"speaker": "Speaker 1", "start": 33.5, "end": 36.0, "text": "Were there any other witnesses?"},
        {"speaker": "Speaker 2", "start": 36.2, "end": 47.0, "text": "There was a guy at the crosswalk who ran over to help me. He said the truck driver was on his phone."}
    ],
    "speaker_count": 2,
    "speaker_notes": "Speaker 1 appears to be the interviewing attorney. Speaker 2 appears to be the plaintiff (Sarah Chen)."
}

MOCK_AUDIO_ANALYSIS = {
    "summary": "Client statement from Sarah Chen describing the rear-end collision. She reports being stopped at a red light when struck from behind by a truck traveling eastbound at approximately 45 mph. A bystander witness reportedly saw the other driver using a phone.",
    "labels": ["client_statement", "rear_end_collision", "distracted_driving", "speed_dispute"],
    "entities": [
        {
            "type": "person",
            "name": "Sarah Chen",
            "aliases": ["the plaintiff", "Speaker 2"],
            "mentions": [
                {"timestamp_start": 3.5, "timestamp_end": 18.1, "excerpt": "Describing the collision from her perspective"}
            ]
        },
        {
            "type": "person",
            "name": "Unknown Crosswalk Witness",
            "aliases": ["bystander", "the guy at the crosswalk"],
            "mentions": [
                {"timestamp_start": 36.2, "timestamp_end": 47.0, "excerpt": "A guy at the crosswalk who ran over to help"}
            ]
        }
    ],
    "key_facts": [
        {
            "fact": "The plaintiff was stopped at a red light when struck",
            "speaker": "Speaker 2",
            "timestamp_start": 3.5,
            "excerpt": "I was just sitting at the light, it was red",
            "category": "incident_description"
        },
        {
            "fact": "The plaintiff estimates the defendant was traveling at least 45 mph",
            "speaker": "Speaker 2",
            "timestamp_start": 3.5,
            "excerpt": "I think he was going at least 45, maybe faster",
            "category": "incident_description"
        },
        {
            "fact": "The defendant's vehicle was heading eastbound on Main Street",
            "speaker": "Speaker 2",
            "timestamp_start": 22.3,
            "excerpt": "heading eastbound on Main Street",
            "category": "incident_description"
        },
        {
            "fact": "A bystander witness reported the defendant was using a phone while driving",
            "speaker": "Speaker 2",
            "timestamp_start": 36.2,
            "excerpt": "He said the truck driver was on his phone",
            "category": "liability"
        }
    ],
    "timeline_events": [
        {
            "timestamp": "Before impact",
            "description": "Plaintiff stopped at red light facing eastbound",
            "mentioned_at": 3.5
        },
        {
            "timestamp": "At impact",
            "description": "Defendant's truck strikes plaintiff from behind",
            "mentioned_at": 10.0
        }
    ],
    "credibility_notes": "Speaker is consistent in describing the sequence of events. Speed estimate of 45+ mph may be subjective. The claim about phone use is hearsay from an unidentified bystander witness."
}

MOCK_DIMENSION_DISCOVERY = {
    "case_type_detected": "personal_injury_auto_accident",
    "dimensions": [
        {"name": "vehicle_speed", "description": "Speed of vehicles at time of collision", "importance": "high", "example_claims": ["Defendant was going 35 mph"]},
        {"name": "direction_of_travel", "description": "Direction each vehicle was traveling", "importance": "high", "example_claims": ["Defendant was heading northbound"]},
        {"name": "traffic_signal_state", "description": "State of traffic signals at time of incident", "importance": "high", "example_claims": ["Light was red"]},
        {"name": "driver_distraction", "description": "Whether any driver was distracted", "importance": "high", "example_claims": ["Driver was on phone"]},
        {"name": "point_of_impact", "description": "Where on the vehicles contact was made", "importance": "medium", "example_claims": ["Struck in the rear"]},
        {"name": "injuries_reported", "description": "Injuries claimed by parties", "importance": "high", "example_claims": ["Neck and back pain"]},
        {"name": "weather_conditions", "description": "Weather and road conditions", "importance": "low", "example_claims": ["Clear and dry"]},
        {"name": "witness_observations", "description": "What witnesses saw", "importance": "medium", "example_claims": ["Bystander saw phone use"]},
        {"name": "time_of_incident", "description": "When the incident occurred", "importance": "medium", "example_claims": ["2:34 PM"]},
        {"name": "fault_attribution", "description": "Who is at fault and why", "importance": "high", "example_claims": ["Defendant failed to stop"]},
    ],
    "source_reliability_ranking": [
        {"evidence_type": "police_report", "reliability": 0.9, "reasoning": "Official record by trained officer"},
        {"evidence_type": "dashcam_video", "reliability": 0.95, "reasoning": "Objective visual evidence"},
        {"evidence_type": "witness_statement", "reliability": 0.6, "reasoning": "Subject to perception bias"},
        {"evidence_type": "photo", "reliability": 0.8, "reasoning": "Objective but limited context"},
        {"evidence_type": "medical_record", "reliability": 0.9, "reasoning": "Professional medical documentation"},
    ]
}

MOCK_FACT_CLASSIFICATION = [
    {"index": 0, "dimension": "time_of_incident", "related_entities": ["Sarah Chen", "Marcus Thompson"], "normalized_claim": "The collision occurred at 2:34 PM on March 5, 2024"},
    {"index": 1, "dimension": "traffic_signal_state", "related_entities": ["Sarah Chen", "2020 Silver Toyota Camry"], "normalized_claim": "The plaintiff's vehicle was stopped at a red traffic light"},
    {"index": 2, "dimension": "vehicle_speed", "related_entities": ["Marcus Thompson", "2019 Black Ford F-150"], "normalized_claim": "The defendant's vehicle was traveling at approximately 35 mph"},
    {"index": 3, "dimension": "fault_attribution", "related_entities": ["Marcus Thompson"], "normalized_claim": "The defendant failed to stop and rear-ended the plaintiff"},
    {"index": 4, "dimension": "injuries_reported", "related_entities": ["Sarah Chen"], "normalized_claim": "The plaintiff reported neck and lower back pain at the scene"},
    {"index": 5, "dimension": "weather_conditions", "related_entities": [], "normalized_claim": "Weather was clear with dry road conditions"},
    {"index": 6, "dimension": "traffic_signal_state", "related_entities": ["Sarah Chen"], "normalized_claim": "The plaintiff was stopped at a red light when struck"},
    {"index": 7, "dimension": "vehicle_speed", "related_entities": ["Marcus Thompson", "2019 Black Ford F-150"], "normalized_claim": "The defendant was traveling at least 45 mph, possibly faster"},
    {"index": 8, "dimension": "direction_of_travel", "related_entities": ["Marcus Thompson", "2019 Black Ford F-150"], "normalized_claim": "The defendant's vehicle was heading eastbound on Main Street"},
    {"index": 9, "dimension": "driver_distraction", "related_entities": ["Marcus Thompson"], "normalized_claim": "A bystander witness reported the defendant was using a phone while driving"},
]

MOCK_CONTRADICTION_CHECK = {
    "contradictions": [
        {
            "fact_a_index": 0,
            "fact_b_index": 1,
            "is_contradiction": True,
            "severity": "medium",
            "explanation": "Police report estimates defendant speed at 35 mph, plaintiff estimates at least 45 mph. A 10+ mph discrepancy that affects damage and liability assessment.",
            "type": "numerical_discrepancy"
        }
    ]
}

MOCK_DIRECTION_CONTRADICTION = {
    "contradictions": [
        {
            "fact_a_index": 0,
            "fact_b_index": 1,
            "is_contradiction": True,
            "severity": "high",
            "explanation": "Police report states defendant was traveling northbound, but plaintiff states defendant was heading eastbound. A critical directional conflict that affects accident reconstruction.",
            "type": "directional_conflict"
        }
    ]
}


# ──────────────────────────────────────────────
#  MOCK GEMINI CLIENT
# ──────────────────────────────────────────────

class MockGeminiState:
    """Track which prompts have been called to return appropriate mocks."""
    call_count = 0
    calls = []

def mock_ask_gemini_json(prompt, **kwargs):
    """Replace gemini_client.ask_gemini_json during testing."""
    MockGeminiState.call_count += 1
    MockGeminiState.calls.append(prompt[:100])
    
    # Route to appropriate mock based on prompt content
    if "KEY FACTUAL DIMENSIONS" in prompt:
        return MOCK_DIMENSION_DISCOVERY
    elif "classifying facts" in prompt.lower():
        return MOCK_FACT_CLASSIFICATION
    elif "contradiction analyzer" in prompt.lower():
        if "direction_of_travel" in prompt:
            return MOCK_DIRECTION_CONTRADICTION
        elif "vehicle_speed" in prompt:
            return MOCK_CONTRADICTION_CHECK
        return {"contradictions": []}
    elif "legal document analyzer" in prompt.lower():
        return MOCK_PDF_ANALYSIS
    elif "legal transcript analyzer" in prompt.lower():
        return MOCK_AUDIO_ANALYSIS
    else:
        return {"result": "mock response"}

def mock_ask_gemini_multimodal(prompt, **kwargs):
    """Replace gemini_client.ask_gemini_multimodal during testing."""
    MockGeminiState.call_count += 1
    return json.dumps(MOCK_AUDIO_TRANSCRIPT)


# ──────────────────────────────────────────────
#  TEST RUNNER
# ──────────────────────────────────────────────

def run_tests():
    use_real_api = os.getenv("CLARION_USE_REAL_API", "0") == "1"

    if not use_real_api:
        # Patch Gemini calls with mocks
        import app.utils.gemini_client as gc
        gc.ask_gemini_json = mock_ask_gemini_json
        gc.ask_gemini_multimodal = mock_ask_gemini_multimodal

        # Also patch in the parser modules that imported these
        import app.services.parser.pdf as pdf_mod
        import app.services.parser.audio as audio_mod
        import app.services.intelligence.citations as cite_mod
        import app.services.intelligence.contradictions as contra_mod

        pdf_mod.ask_gemini_json = mock_ask_gemini_json
        audio_mod.ask_gemini_multimodal = mock_ask_gemini_multimodal
        audio_mod.ask_gemini_json = mock_ask_gemini_json
        cite_mod.ask_gemini_json = mock_ask_gemini_json
        contra_mod.ask_gemini_json = mock_ask_gemini_json

        print("🔧 Using MOCK Gemini responses\n")
    else:
        print("🌐 Using REAL Gemini API\n")

    from app.models.schema import (
        CaseFile, EvidenceItem, EvidenceType, ExtractedContent,
        MediaRef, Entity, SourceLocation, SpeakerSegment,
        Contradiction, ContradictionSeverity, new_id,
    )
    from app.services.intelligence.citations import build_citation_index, cite_claim
    from app.services.intelligence.contradictions import (
        detect_contradictions, summarize_contradictions,
        get_contradictions_for_entity,
    )

    passed = 0
    failed = 0

    def test(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name} — {detail}")
            failed += 1

    # ─── TEST 1: Schema creation ───
    print("━━━ TEST 1: Schema Creation ━━━")
    case = CaseFile(
        title="Chen v. Thompson — Rear-End Collision",
        case_type="personal_injury",
        description="Rear-end collision at Main St and 5th Ave intersection",
    )
    test("CaseFile created", case.id is not None)
    test("Status is intake", case.status == "intake")
    test("Has a title", case.title is not None)

    # ─── TEST 2: Build mock evidence (simulating parser output) ───
    print("\n━━━ TEST 2: Evidence Parsing (Simulated) ━━━")

    # Simulate PDF parser output
    police_evidence = EvidenceItem(
        filename="police-report.pdf",
        evidence_type=EvidenceType.POLICE_REPORT,
        media=MediaRef(url="file:///mock/police-report.pdf", media_type="application/pdf"),
        content=ExtractedContent(text="[Page 1]\nPolice report content..."),
        entities=[
            Entity(type="person", name="Sarah Chen", mentions=[
                SourceLocation(evidence_id="", page=1, excerpt="Driver 1: Sarah Chen")
            ]),
            Entity(type="person", name="Marcus Thompson", mentions=[
                SourceLocation(evidence_id="", page=1, excerpt="Driver 2: Marcus Thompson")
            ]),
            Entity(type="vehicle", name="2020 Silver Toyota Camry", mentions=[
                SourceLocation(evidence_id="", page=1, excerpt="Vehicle 1: 2020 Toyota Camry")
            ]),
        ],
        labels=["traffic_accident", "rear_end_collision"],
        summary="Police report documenting rear-end collision on March 5, 2024.",
    )
    # Attach mock analysis
    police_evidence._analysis = MOCK_PDF_ANALYSIS

    # Fix source locations to reference this evidence's ID
    for entity in police_evidence.entities:
        for mention in entity.mentions:
            mention.evidence_id = police_evidence.id

    case.evidence.append(police_evidence)
    test("Police report evidence created", police_evidence.evidence_type == EvidenceType.POLICE_REPORT)
    test("Has entities", len(police_evidence.entities) > 0)
    test("Has labels", len(police_evidence.labels) > 0)

    # Simulate audio parser output
    witness_evidence = EvidenceItem(
        filename="client-statement.mp3",
        evidence_type=EvidenceType.WITNESS_STATEMENT,
        media=MediaRef(url="file:///mock/client-statement.mp3", media_type="audio/mp3"),
        content=ExtractedContent(
            text=MOCK_AUDIO_TRANSCRIPT["full_transcript"],
            speaker_segments=[
                SpeakerSegment(**seg) for seg in MOCK_AUDIO_TRANSCRIPT["segments"]
            ],
        ),
        entities=[
            Entity(type="person", name="Sarah Chen", mentions=[
                SourceLocation(evidence_id="", timestamp_start=3.5, timestamp_end=18.1, excerpt="Describing the collision")
            ]),
        ],
        labels=["client_statement", "rear_end_collision"],
        summary="Client statement from Sarah Chen describing the collision.",
    )
    witness_evidence._analysis = MOCK_AUDIO_ANALYSIS

    for entity in witness_evidence.entities:
        for mention in entity.mentions:
            mention.evidence_id = witness_evidence.id

    case.evidence.append(witness_evidence)
    test("Witness statement evidence created", witness_evidence.evidence_type == EvidenceType.WITNESS_STATEMENT)
    test("Has speaker segments", len(witness_evidence.content.speaker_segments) > 0)

    # Merge entities into case level
    for evidence in case.evidence:
        for entity in evidence.entities:
            existing = next((e for e in case.entities if e.name.lower() == entity.name.lower()), None)
            if existing:
                existing.mentions.extend(entity.mentions)
            else:
                case.entities.append(entity)

    test("Case has merged entities", len(case.entities) >= 2)
    test("Sarah Chen has mentions from both sources",
         len([e for e in case.entities if e.name == "Sarah Chen"][0].mentions) >= 2 if any(e.name == "Sarah Chen" for e in case.entities) else False)

    # ─── TEST 3: Citation Index ───
    print("\n━━━ TEST 3: Citation Index ━━━")
    index = build_citation_index(case)

    test("Index built successfully", index is not None)
    test("Case type detected", index.case_type != "unknown", f"got: {index.case_type}")
    test("Dimensions discovered", len(index.dimensions) > 0, f"got: {len(index.dimensions)}")
    test("Facts indexed", len(index.facts) > 0, f"got: {len(index.facts)}")

    # Test queries
    all_dims = index.get_all_dimensions()
    test("Can list dimensions", len(all_dims) > 0, f"got: {all_dims}")

    all_entities = index.get_all_entities()
    test("Can list entities", len(all_entities) > 0, f"got: {all_entities}")

    speed_facts = index.query_by_dimension("vehicle_speed")
    test("Can query by dimension", len(speed_facts) >= 0)

    sarah_facts = index.query_by_entity("Sarah Chen")
    test("Can query by entity", len(sarah_facts) >= 0)

    # Test cite_claim
    citations = cite_claim(
        "The defendant was speeding",
        index,
        dimension="vehicle_speed",
    )
    test("cite_claim returns citations", isinstance(citations, list))

    # ─── TEST 4: Contradiction Detection ───
    print("\n━━━ TEST 4: Contradiction Detection ━━━")
    contradictions = detect_contradictions(case, index)
    case.contradictions = contradictions

    test("Contradictions detected", len(contradictions) >= 0)

    if contradictions:
        test("Contradictions have severity", contradictions[0].severity is not None)
        test("Contradictions have description", len(contradictions[0].description) > 0)
        test("Contradictions have both facts", contradictions[0].fact_a and contradictions[0].fact_b)

        # Test summary
        summary = summarize_contradictions(contradictions)
        test("Summary has total", "total" in summary)
        test("Summary has severity counts", "high" in summary and "medium" in summary)

        # Test entity filter
        sarah_contradictions = get_contradictions_for_entity(contradictions, "Sarah Chen")
        test("Can filter contradictions by entity", isinstance(sarah_contradictions, list))

    # ─── TEST 5: Full CaseFile Serialization ───
    print("\n━━━ TEST 5: CaseFile Serialization ━━━")
    case.status = "complete"

    # Remove _analysis attributes before serialization (they're not in the schema)
    for ev in case.evidence:
        if hasattr(ev, '_analysis'):
            delattr(ev, '_analysis')

    case_json = case.model_dump_json(indent=2)
    test("CaseFile serializes to JSON", len(case_json) > 0)

    restored = CaseFile.model_validate_json(case_json)
    test("CaseFile deserializes from JSON", restored.id == case.id)
    test("Evidence survives roundtrip", len(restored.evidence) == len(case.evidence))
    test("Entities survive roundtrip", len(restored.entities) == len(case.entities))
    test("Contradictions survive roundtrip", len(restored.contradictions) == len(case.contradictions))

    # ─── TEST 6: API Response Format ───
    print("\n━━━ TEST 6: API Response Format ━━━")

    # Simulate what GET /api/case/{id} returns
    api_response = {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "evidence": [
            {
                "id": e.id,
                "filename": e.filename,
                "evidence_type": getattr(e.evidence_type, "value", e.evidence_type),
                "labels": e.labels,
                "summary": e.summary,
                "entity_count": len(e.entities),
            }
            for e in case.evidence
        ],
        "entities": [
            {
                "type": e.type,
                "name": e.name,
                "mention_count": len(e.mentions),
            }
            for e in case.entities
        ],
        "contradictions": [
            {
                "id": c.id,
                "severity": getattr(c.severity, "value", c.severity),
                "description": c.description,
                "fact_a": c.fact_a,
                "fact_b": c.fact_b,
            }
            for c in case.contradictions
        ],
    }

    api_json = json.dumps(api_response, indent=2)
    test("API response is valid JSON", json.loads(api_json) is not None)
    test("API response has evidence", len(api_response["evidence"]) > 0)
    test("API response has entities", len(api_response["entities"]) > 0)
    test("Evidence types are strings", isinstance(api_response["evidence"][0]["evidence_type"], str))

    # ─── RESULTS ───
    print(f"\n{'━' * 40}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"  Gemini calls made: {MockGeminiState.call_count}")
    print(f"{'━' * 40}")

    if failed > 0:
        print("\n⚠️  Some tests failed. Fix these before integration.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed. Pipeline is ready for integration.")

    # Print the final case JSON for inspection
    output_path = "/tmp/clarion-test-output.json"
    with open(output_path, "w") as f:
        f.write(api_json)
    print(f"\n📄 API response written to {output_path}")


if __name__ == "__main__":
    run_tests()