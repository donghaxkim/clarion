from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    ReportBlock,
    ReportBlockType,
    ReportDocument,
    ReportProvenance,
    ReportStatus,
    SourceSpan,
)
from app.services.generation.report_citations import (
    build_evidence_citation,
    build_public_context_citation,
    normalize_report_document,
    validate_canonical_citations,
)


def test_build_evidence_citation_uses_evidence_title_and_source_span_excerpt():
    bundle = CaseEvidenceBundle(
        case_id="case-1",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                kind=EvidenceItemType.transcript,
                title="Witness Transcript",
                summary="Summary should not win when a source span exists.",
                source_spans=[
                    SourceSpan(segment_id="seg-1", snippet="The light was red when the impact happened."),
                ],
            )
        ],
    )

    citation = build_evidence_citation(
        "ev-1",
        bundle=bundle,
        segment_id="seg-1",
    )

    assert citation.source_label == "Witness Transcript"
    assert citation.excerpt == "The light was red when the impact happened."
    assert citation.snippet == citation.excerpt


def test_build_evidence_citation_can_use_document_excerpt_when_explicitly_allowed():
    bundle = CaseEvidenceBundle(
        case_id="case-1",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-2",
                kind=EvidenceItemType.transcript,
                metadata={"filename": "uploaded-statement.txt"},
                extracted_text="A" * 300,
            )
        ],
    )

    citation = build_evidence_citation(
        "ev-2",
        bundle=bundle,
        allow_document_excerpt=True,
    )

    assert citation.source_label == "uploaded-statement.txt"
    assert citation.excerpt.endswith("...")
    assert len(citation.excerpt) <= 220


def test_build_public_context_citation_uses_hostname_and_fallback_excerpt():
    citation = build_public_context_citation(
        "road safety standards",
        uri="https://www.nhtsa.gov/safety/seat-belts",
        fallback_excerpt="Seat belt guidance published by NHTSA.",
    )

    assert citation.source_label == "www.nhtsa.gov"
    assert citation.excerpt == "Seat belt guidance published by NHTSA."


def test_normalize_report_document_strips_sparse_legacy_citations():
    bundle = CaseEvidenceBundle(
        case_id="case-1",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                kind=EvidenceItemType.transcript,
                title="Witness Transcript",
                summary="The witness says the defendant ran the red light.",
            )
        ],
    )
    report = ReportDocument(
        report_id="report-1",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="block-1",
                type=ReportBlockType.text,
                title="Incident summary",
                content="The defendant entered against the signal.",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
                citations=[Citation(source_id="ev-1")],
            )
        ],
    )

    normalized, changed = normalize_report_document(report, bundle=bundle)

    assert changed is True
    assert normalized.sections[0].citations == []


def test_normalize_report_document_keeps_last_duplicate_section_id():
    report = ReportDocument(
        report_id="report-1",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="image-impact",
                type=ReportBlockType.image,
                title="Impact still",
                content=None,
                sort_key="0001",
                provenance=ReportProvenance.evidence,
            ),
            ReportBlock(
                id="image-impact",
                type=ReportBlockType.image,
                title="Impact still",
                content="Canonical prompt-bearing block",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
            ),
        ],
    )

    normalized, changed = normalize_report_document(report)

    assert changed is True
    assert len(normalized.sections) == 1
    assert normalized.sections[0].id == "image-impact"
    assert normalized.sections[0].content == "Canonical prompt-bearing block"


def test_validate_canonical_citations_rejects_blank_display_fields():
    try:
        validate_canonical_citations(
            [
                Citation(
                    source_id="ev-1",
                    source_label="   ",
                    excerpt="",
                    provenance=ReportProvenance.evidence,
                )
            ]
        )
    except ValueError as exc:
        assert "missing source_label" in str(exc)
    else:
        raise AssertionError("Expected canonical citation validation to fail")
