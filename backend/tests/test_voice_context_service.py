from app.models import (
    CaseEvidenceBundle,
    EntityMention,
    EvidenceItem as ReportEvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
    ReportBlock,
    ReportDocument,
    ReportStatus,
)
from app.models.schema import (
    Contradiction,
    Entity,
    EvidenceItem,
    ExtractedContent,
    MediaRef,
    MissingInfo,
    SourceLocation,
    SourcePin,
)
from app.services import case_service as case_service_module
from app.services.case_service import CaseWorkspaceService, InMemoryCaseWorkspaceBackend
from app.services.generation.job_store import ReportJobStore
from app.services.intelligence.citations import CitationIndex, IndexedFact
from app.services.voice.context_service import VoiceContextService
from app.models import EvidenceType


def _make_case_evidence() -> EvidenceItem:
    return EvidenceItem(
        id="ev_legacy",
        filename="witness_statement.txt",
        evidence_type="witness_statement",
        media=MediaRef(url="file:///tmp/witness.txt", media_type="text/plain"),
        content=ExtractedContent(text="John Smith says the vehicle was traveling 25 mph."),
        summary="Legacy witness statement",
        entities=[
            Entity(
                id="ent_legacy",
                type="person",
                name="John Smith",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_legacy",
                        page=1,
                        excerpt="John Smith says the vehicle was traveling 25 mph.",
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
            fact_id="fact_legacy",
            fact_text="John Smith says the vehicle was traveling 25 mph.",
            dimension="speed",
            related_entities=["John Smith"],
            source_location=SourceLocation(
                evidence_id="ev_legacy",
                page=1,
                excerpt="John Smith says the vehicle was traveling 25 mph.",
            ),
            evidence_type=EvidenceType.WITNESS_STATEMENT,
            category="speed",
            excerpt="John Smith says the vehicle was traveling 25 mph.",
            reliability=0.6,
        )
    )
    return index


def test_voice_context_service_uses_report_and_case_state(monkeypatch, tmp_path):
    case_service = CaseWorkspaceService(backend=InMemoryCaseWorkspaceBackend())
    record = case_service.create_case(
        title="Smith v. Johnson",
        case_type="personal_injury",
        description="Rear-end collision at an intersection.",
    )
    case_service.attach_evidence(record.case.id, _make_case_evidence())

    monkeypatch.setattr(case_service_module, "build_citation_index", lambda case: _make_index())
    monkeypatch.setattr(
        case_service_module,
        "detect_contradictions",
        lambda case, index: [
            Contradiction(
                id="contr_001",
                severity="high",
                description="Speed estimate conflicts for John Smith",
                source_a=SourcePin(evidence_id="ev_legacy", detail="Page 1"),
                source_b=SourcePin(evidence_id="ev_002", detail="Page 2"),
                fact_a="John Smith says the vehicle was traveling 25 mph.",
                fact_b="Police report says the vehicle was traveling 40 mph.",
            )
        ],
    )
    monkeypatch.setattr(
        case_service_module,
        "find_gaps",
        lambda case, index: [
            MissingInfo(
                id="gap_001",
                severity="warning",
                description="Need clearer braking distance evidence.",
                recommendation="Obtain scene measurements.",
            )
        ],
    )
    case_service.analyze_case(record.case.id)

    report_store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(
        report_id="report_001",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="section_001",
                type="text",
                title="Collision Summary",
                content="Vehicle A struck Vehicle B from behind.",
                sort_key="0001",
                citations=[],
            )
        ],
    )
    job = report_store.create_job(report=report)
    report_store.save_request(
        job.job_id,
        GenerateReportRequest(
            bundle=CaseEvidenceBundle(
                case_id=record.case.id,
                case_summary="Rear-end collision at an intersection.",
                evidence_items=[
                    ReportEvidenceItem(
                        evidence_id="ev_request",
                        kind=EvidenceItemType.transcript,
                        title="Request evidence",
                        summary="Request bundle evidence",
                        extracted_text="This should be superseded by case evidence.",
                    )
                ],
                entities=[
                    EntityMention(
                        entity_id="ent_request",
                        name="John Smith",
                        role="person",
                    )
                ],
            ),
            user_id="user-1",
        ),
    )

    service = VoiceContextService(report_store=report_store, case_service=case_service)
    context = service.get_context(report.report_id, focused_section_id="section_001")

    assert context is not None
    assert context.report_id == "report_001"
    assert context.case_id == record.case.id
    assert context.title == "Smith v. Johnson"
    assert context.case_type == "personal_injury"
    assert context.status == "completed"
    assert context.sections[0].section_id == "section_001--heading"
    assert context.sections[1].section_id == "section_001"
    assert context.focused_section is not None
    assert context.focused_section.section_id == "section_001"
    assert context.evidence[0].evidence_id == "ev_legacy"
    assert context.entities[0].name == "John Smith"
    assert context.entities[0].facts[0].fact == "John Smith says the vehicle was traveling 25 mph."
    assert context.contradictions[0].contradiction_id == "contr_001"
    assert context.missing_info[0].item_id == "gap_001"


def test_voice_context_service_returns_none_for_unknown_report(tmp_path):
    service = VoiceContextService(
        report_store=ReportJobStore(str(tmp_path / "jobs.json")),
        case_service=CaseWorkspaceService(backend=InMemoryCaseWorkspaceBackend()),
    )

    assert service.get_context("missing-report") is None
