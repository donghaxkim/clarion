from fastapi.testclient import TestClient

from app.main import app
from app.models.schema import (
    Contradiction,
    Entity,
    EvidenceItem,
    ExtractedContent,
    MediaRef,
    SourceLocation,
    SourcePin,
)
from app.services import case_service as case_service_module
from app.services.case_service import case_workspace_service
from app.services.intelligence.citations import CitationIndex, IndexedFact
from app.models import EvidenceType


def _make_evidence() -> EvidenceItem:
    return EvidenceItem(
        id="ev_001",
        filename="witness_statement.txt",
        evidence_type="witness_statement",
        media=MediaRef(url="file:///tmp/witness.txt", media_type="text/plain"),
        content=ExtractedContent(text="John Smith says the car was moving at 25 mph."),
        summary="Witness statement about vehicle speed",
        entities=[
            Entity(
                id="ent_001",
                type="person",
                name="John Smith",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_001",
                        page=1,
                        excerpt="John Smith says the car was moving at 25 mph.",
                    )
                ],
            )
        ],
    )


def _make_index() -> CitationIndex:
    index = CitationIndex()
    index.case_type = "personal_injury"
    index.dimensions = [{"name": "speed", "description": "Vehicle speed"}]
    index.add_fact(
        IndexedFact(
            fact_id="fact_001",
            fact_text="John Smith says the car was moving at 25 mph.",
            dimension="speed",
            related_entities=["John Smith"],
            source_location=SourceLocation(
                evidence_id="ev_001",
                page=1,
                excerpt="John Smith says the car was moving at 25 mph.",
            ),
            evidence_type=EvidenceType.WITNESS_STATEMENT,
            category="speed",
            excerpt="John Smith says the car was moving at 25 mph.",
            reliability=0.6,
        )
    )
    return index


def _make_contradiction() -> Contradiction:
    return Contradiction(
        id="contr_001",
        severity="high",
        description="Speed estimate conflicts for John Smith",
        source_a=SourcePin(evidence_id="ev_001", detail="Page 1"),
        source_b=SourcePin(evidence_id="ev_002", detail="Page 2"),
        fact_a="John Smith says the car was moving at 25 mph.",
        fact_b="Police report says the car was moving at 40 mph.",
    )


def setup_function():
    case_workspace_service.clear()


def teardown_function():
    case_workspace_service.clear()


def test_create_and_get_case():
    client = TestClient(app)

    create_response = client.post(
        "/cases",
        json={
            "title": "Smith v. Johnson",
            "case_type": "personal_injury",
            "description": "Rear-end collision at an intersection.",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["case_id"]
    assert created["status"] == "intake"

    case_response = client.get(f"/cases/{created['case_id']}")
    assert case_response.status_code == 200
    payload = case_response.json()
    assert payload["title"] == "Smith v. Johnson"
    assert payload["case_type"] == "personal_injury"
    assert payload["description"] == "Rear-end collision at an intersection."
    assert payload["evidence"] == []


def test_analyze_case_and_fetch_entity_details(monkeypatch):
    record = case_workspace_service.create_case(
        title="Smith v. Johnson",
        case_type="personal_injury",
        description="Rear-end collision at an intersection.",
    )
    case_workspace_service.attach_evidence(record.case.id, _make_evidence())

    monkeypatch.setattr(case_service_module, "build_citation_index", lambda case: _make_index())
    monkeypatch.setattr(
        case_service_module,
        "detect_contradictions",
        lambda case, index: [_make_contradiction()],
    )

    client = TestClient(app)
    analyze_response = client.post(f"/cases/{record.case.id}/analyze")
    assert analyze_response.status_code == 200
    analyzed = analyze_response.json()
    assert analyzed["case_type_detected"] == "personal_injury"
    assert analyzed["total_facts_indexed"] == 1
    assert analyzed["contradictions"]["summary"]["high"] == 1
    assert analyzed["entities"][0]["name"] == "John Smith"

    entity_response = client.get(f"/cases/{record.case.id}/entities/John Smith")
    assert entity_response.status_code == 200
    entity_payload = entity_response.json()
    assert entity_payload["entity"]["name"] == "John Smith"
    assert entity_payload["facts"][0]["dimension"] == "speed"
    assert entity_payload["contradictions"][0]["id"] == "contr_001"
