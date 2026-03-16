from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models import Citation, ReportBlock, ReportBlockType, ReportDocument, ReportGenerationJobStatus
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
from app.routers import generate
from app.services.case_service import InMemoryCaseWorkspaceBackend, case_workspace_service
from app.services.generation.job_store import ReportJobStore
from app.services.intelligence.citations import CitationIndex, IndexedFact
from app.models import EvidenceType


class _RecordingDispatcher:
    def __init__(self):
        self.job_ids: list[str] = []
        self.analysis_calls: list[tuple[str, int]] = []

    def dispatch_report_job(self, job_id: str) -> str:
        self.job_ids.append(job_id)
        return f"report-{job_id}"

    def dispatch_case_analysis(self, case_id: str, evidence_revision: int) -> str:
        self.analysis_calls.append((case_id, evidence_revision))
        return f"analysis-{case_id}-{evidence_revision}"


def _make_evidence() -> EvidenceItem:
    evidence = EvidenceItem(
        id="ev_001",
        filename="witness_statement.txt",
        evidence_type="witness_statement",
        media=MediaRef(url="file:///tmp/witness.txt", media_type="text/plain"),
        content=ExtractedContent(
            text=(
                "[Page 1]\n"
                "John Smith says the car was moving at 25 mph.\n"
                "The light was yellow when the sedan entered the intersection.\n"
                "John Smith had a clear view of the westbound lanes and nothing was blocking his view.\n"
                "The pickup started its left turn before the lane was clear.\n"
                "The sedan braked before impact and struck the pickup near the center of the intersection.\n"
            )
        ),
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
    evidence._analysis = {
        "summary": "Witness statement describing the collision.",
        "labels": ["traffic_accident", "intersection_collision"],
        "key_facts": [
            {
                "fact": "The traffic light was yellow when the sedan entered the intersection.",
                "page": 1,
                "excerpt": "The light was yellow when the sedan entered the intersection.",
                "category": "incident_description",
            },
            {
                "fact": "The witness had a clear, unobstructed view of the westbound lanes.",
                "page": 1,
                "excerpt": "John Smith had a clear view of the westbound lanes and nothing was blocking his view.",
                "category": "witness_account",
            },
            {
                "fact": "The pickup started its left turn before the lane was clear.",
                "page": 1,
                "excerpt": "The pickup started its left turn before the lane was clear.",
                "category": "liability",
            },
            {
                "fact": "The sedan braked before impact and struck the pickup near the center of the intersection.",
                "page": 1,
                "excerpt": "The sedan braked before impact and struck the pickup near the center of the intersection.",
                "category": "incident_description",
            },
        ],
        "timeline_events": [
            {
                "timestamp": "2:30 PM",
                "description": "Incident occurs at the intersection.",
                "page": 1,
            },
            {
                "timestamp": "3:00 PM",
                "description": "Witness statement recorded by the investigator.",
                "page": 1,
            },
        ],
    }
    return evidence


def _make_secondary_evidence() -> EvidenceItem:
    return EvidenceItem(
        id="ev_002",
        filename="driver_statement.txt",
        evidence_type="witness_statement",
        media=MediaRef(url="file:///tmp/driver_statement.txt", media_type="text/plain"),
        content=ExtractedContent(text="Marcus Thompson says he braked before impact."),
        summary="Driver statement about the collision",
        entities=[
            Entity(
                id="ent_002",
                type="person",
                name="Marcus Thompson",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_002",
                        page=1,
                        excerpt="Marcus Thompson says he braked before impact.",
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


@pytest.fixture(autouse=True)
def _use_in_memory_case_workspace():
    original_backend = case_workspace_service._backend
    case_workspace_service._backend = InMemoryCaseWorkspaceBackend()
    case_workspace_service.clear()
    try:
        yield
    finally:
        case_workspace_service.clear()
        case_workspace_service._backend = original_backend


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
    assert entity_payload["mentions"][0]["source"] == "witness_statement.txt"
    assert entity_payload["facts"][0]["dimension"] == "speed"
    assert entity_payload["facts"][0]["source"] == "witness_statement.txt"
    assert entity_payload["contradictions"][0]["id"] == "contr_001"


def test_case_report_job_routes_bind_case_to_generate_flow(monkeypatch, tmp_path):
    record = case_workspace_service.create_case(
        title="Smith v. Johnson",
        case_type="personal_injury",
        description="Rear-end collision at an intersection.",
    )
    case_workspace_service.attach_evidence(record.case.id, _make_evidence())

    store = ReportJobStore(str(tmp_path / "jobs.json"))
    dispatcher = _RecordingDispatcher()
    monkeypatch.setattr(generate, "job_store", store)
    monkeypatch.setattr(generate, "dispatcher", dispatcher)

    client = TestClient(app)
    create_response = client.post(f"/cases/{record.case.id}/report-jobs")

    assert create_response.status_code == 202
    created = create_response.json()
    assert created["case_id"] == record.case.id
    assert created["job_id"]
    assert created["report_id"]
    assert dispatcher.job_ids == [created["job_id"]]
    assert dispatcher.analysis_calls == [(record.case.id, 1)]

    case_response = client.get(f"/cases/{record.case.id}")
    assert case_response.status_code == 200
    case_payload = case_response.json()
    assert case_payload["latest_report_job_id"] == created["job_id"]
    assert case_payload["latest_report_id"] == created["report_id"]
    assert case_payload["analysis_status"] == "queued"
    assert case_payload["evidence_revision"] == 1

    report_response = client.get(f"/cases/{record.case.id}/report")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["case_id"] == record.case.id
    assert report_payload["job_id"] == created["job_id"]
    assert report_payload["report_id"] == created["report_id"]
    assert report_payload["status"] == ReportGenerationJobStatus.queued

    request_payload = store.load_request(created["job_id"])
    assert request_payload.bundle.evidence_items[0].source_spans
    assert request_payload.bundle.evidence_items[0].metadata["key_facts"]
    assert {candidate.event_id for candidate in request_payload.bundle.event_candidates} >= {
        "signal_state",
        "collision_sequence",
    }


def test_get_case_returns_report_relevant_entities(monkeypatch, tmp_path):
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
    case_workspace_service.analyze_case(record.case.id)

    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(
        report_id="report-123",
        sections=[
            ReportBlock(
                id="block-1",
                type=ReportBlockType.text,
                title="Witness account",
                content="John Smith says the car was moving at 25 mph.",
                sort_key="2024-01-01T00:00:00Z",
                citations=[
                    Citation(
                        source_id="ev_001",
                        snippet="John Smith says the car was moving at 25 mph.",
                    )
                ],
            )
        ],
    )
    job = store.create_job(report=report, activity=None, workflow=None)
    case_workspace_service.record_latest_report_refs(
        record.case.id,
        report_id=report.report_id,
        job_id=job.job_id,
    )
    monkeypatch.setattr(generate, "job_store", store)

    client = TestClient(app)
    response = client.get(f"/cases/{record.case.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_status"] == "completed"
    assert payload["report_relevant_entities"][0]["name"] == "John Smith"


def test_get_case_includes_entities_from_contradictions_in_cited_evidence(monkeypatch, tmp_path):
    record = case_workspace_service.create_case(
        title="Smith v. Johnson",
        case_type="personal_injury",
        description="Rear-end collision at an intersection.",
    )
    case_workspace_service.attach_evidence(record.case.id, _make_evidence())
    case_workspace_service.attach_evidence(record.case.id, _make_secondary_evidence())

    monkeypatch.setattr(case_service_module, "build_citation_index", lambda case: _make_index())
    monkeypatch.setattr(
        case_service_module,
        "detect_contradictions",
        lambda case, index: [
            Contradiction(
                id="contr_002",
                severity="medium",
                description="Marcus Thompson's speed account conflicts across sources",
                source_a=SourcePin(evidence_id="ev_001", detail="Page 1"),
                source_b=SourcePin(evidence_id="ev_002", detail="Page 1"),
                fact_a="Marcus Thompson was traveling too fast for conditions.",
                fact_b="Marcus Thompson says he braked and was driving carefully.",
            )
        ],
    )
    case_workspace_service.analyze_case(record.case.id)

    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(
        report_id="report-456",
        sections=[
            ReportBlock(
                id="block-1",
                type=ReportBlockType.text,
                title="Witness account",
                content="John Smith says the car was moving at 25 mph.",
                sort_key="2024-01-01T00:00:00Z",
                citations=[
                    Citation(
                        source_id="ev_001",
                        snippet="John Smith says the car was moving at 25 mph.",
                    )
                ],
            )
        ],
    )
    job = store.create_job(report=report, activity=None, workflow=None)
    case_workspace_service.record_latest_report_refs(
        record.case.id,
        report_id=report.report_id,
        job_id=job.job_id,
    )
    monkeypatch.setattr(generate, "job_store", store)

    client = TestClient(app)
    response = client.get(f"/cases/{record.case.id}")

    assert response.status_code == 200
    payload = response.json()
    assert {entity["name"] for entity in payload["report_relevant_entities"]} == {
        "John Smith",
        "Marcus Thompson",
    }
