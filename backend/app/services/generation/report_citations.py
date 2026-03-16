from __future__ import annotations

from typing import Iterable
from urllib.parse import urlparse

from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    ReportDocument,
    ReportProvenance,
)

DEFAULT_EXCERPT = "Excerpt unavailable."
_EXCERPT_MAX_LENGTH = 220


def build_evidence_citation(
    source_id: str,
    *,
    bundle: CaseEvidenceBundle | None = None,
    source_label: str | None = None,
    excerpt: str | None = None,
    segment_id: str | None = None,
    page_number: int | None = None,
    time_range_ms: list[int] | tuple[int, int] | None = None,
    uri: str | None = None,
    allow_document_excerpt: bool = False,
) -> Citation | None:
    trusted_excerpt = _clean(excerpt)
    if trusted_excerpt is None and allow_document_excerpt:
        trusted_excerpt = _evidence_document_excerpt(_evidence_lookup(bundle).get(source_id))
    citation = Citation(
        source_id=source_id,
        source_label=_clean(source_label),
        excerpt=trusted_excerpt,
        segment_id=segment_id,
        page_number=page_number,
        time_range_ms=list(time_range_ms) if time_range_ms is not None else None,
        snippet=trusted_excerpt,
        uri=uri,
        provenance=ReportProvenance.evidence,
    )
    return normalize_citation(citation, bundle=bundle)


def build_public_context_citation(
    source_id: str,
    *,
    source_label: str | None = None,
    excerpt: str | None = None,
    uri: str | None = None,
    fallback_excerpt: str | None = None,
) -> Citation:
    citation = Citation(
        source_id=source_id,
        source_label=_clean(source_label),
        excerpt=_clean(excerpt),
        snippet=_clean(excerpt),
        uri=uri,
        provenance=ReportProvenance.public_context,
    )
    return normalize_citation(citation, fallback_excerpt=fallback_excerpt)


def normalize_report_document(
    report: ReportDocument,
    *,
    bundle: CaseEvidenceBundle | None = None,
) -> tuple[ReportDocument, bool]:
    changed = False
    sections = []

    for block in report.sections:
        fallback_excerpt = block.content or block.title
        citations, citations_changed = normalize_citations(
            block.citations,
            bundle=bundle,
            provenance=block.provenance,
            fallback_excerpt=fallback_excerpt,
        )
        if citations_changed:
            changed = True
            sections.append(block.model_copy(update={"citations": citations}))
        else:
            sections.append(block)

    if not changed:
        return report, False
    return report.model_copy(update={"sections": sections}), True


def normalize_citations(
    citations: Iterable[Citation],
    *,
    bundle: CaseEvidenceBundle | None = None,
    provenance: ReportProvenance | None = None,
    fallback_excerpt: str | None = None,
) -> tuple[list[Citation], bool]:
    evidence_lookup = _evidence_lookup(bundle)
    normalized: list[Citation] = []
    changed = False

    for citation in citations:
        next_citation = normalize_citation(
            citation,
            evidence_lookup=evidence_lookup,
            provenance=provenance,
            fallback_excerpt=fallback_excerpt,
        )
        if next_citation is None:
            changed = True
            continue
        if next_citation.model_dump(mode="json") != citation.model_dump(mode="json"):
            changed = True
        normalized.append(next_citation)

    validate_canonical_citations(normalized)
    return normalized, changed


def normalize_citation(
    citation: Citation,
    *,
    bundle: CaseEvidenceBundle | None = None,
    evidence_lookup: dict[str, EvidenceItem] | None = None,
    provenance: ReportProvenance | None = None,
    fallback_excerpt: str | None = None,
) -> Citation | None:
    resolved_provenance = provenance or citation.provenance
    if evidence_lookup is None:
        evidence_lookup = _evidence_lookup(bundle)
    evidence = evidence_lookup.get(citation.source_id)

    if resolved_provenance == ReportProvenance.evidence:
        source_label = _clean(citation.source_label) or _evidence_source_label(evidence) or citation.source_id
        excerpt = _clean(citation.excerpt) or _clean(citation.snippet) or _evidence_excerpt(citation, evidence)
        if excerpt is None:
            return None
        uri = citation.uri or (evidence.source_uri if evidence is not None else None) or (
            evidence.media_uri if evidence is not None else None
        )
    else:
        source_label = (
            _clean(citation.source_label)
            or _public_context_source_label(citation)
            or citation.source_id
        )
        excerpt = (
            _clean(citation.excerpt)
            or _clean(citation.snippet)
            or _clean(fallback_excerpt)
            or DEFAULT_EXCERPT
        )
        uri = citation.uri

    normalized = citation.model_copy(
        update={
            "provenance": resolved_provenance,
            "source_label": source_label,
            "excerpt": excerpt,
            "snippet": excerpt,
            "uri": uri,
        }
    )
    validate_canonical_citations([normalized])
    return normalized


def validate_canonical_citations(citations: Iterable[Citation]) -> None:
    for citation in citations:
        if not _clean(citation.source_label):
            raise ValueError(
                f"Canonical citation for {citation.source_id!r} is missing source_label"
            )
        if not _clean(citation.excerpt):
            raise ValueError(
                f"Canonical citation for {citation.source_id!r} is missing excerpt"
            )


def _evidence_lookup(bundle: CaseEvidenceBundle | None) -> dict[str, EvidenceItem]:
    if bundle is None:
        return {}
    return {item.evidence_id: item for item in bundle.evidence_items}


def _evidence_source_label(evidence: EvidenceItem | None) -> str | None:
    if evidence is None:
        return None
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    return (
        _clean(evidence.title)
        or _clean(metadata.get("title"))
        or _clean(metadata.get("filename"))
    )


def _evidence_excerpt(citation: Citation, evidence: EvidenceItem | None) -> str | None:
    if evidence is None:
        return None

    for span in evidence.source_spans:
        if citation.segment_id and span.segment_id == citation.segment_id and _clean(span.snippet):
            return _clean(span.snippet)

    for span in evidence.source_spans:
        if citation.page_number and span.page_number == citation.page_number and _clean(span.snippet):
            return _clean(span.snippet)

    for span in evidence.source_spans:
        if citation.time_range_ms and span.time_range_ms == citation.time_range_ms and _clean(span.snippet):
            return _clean(span.snippet)

    return None


def _evidence_document_excerpt(evidence: EvidenceItem | None) -> str | None:
    if evidence is None:
        return None
    return _clean(evidence.summary) or _truncate_excerpt(evidence.extracted_text)


def _public_context_source_label(citation: Citation) -> str | None:
    if _clean(citation.uri):
        parsed = urlparse(citation.uri)
        return _clean(parsed.hostname)
    return None


def _truncate_excerpt(value: str | None) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if len(text) <= _EXCERPT_MAX_LENGTH:
        return text
    return f"{text[: _EXCERPT_MAX_LENGTH - 3].rstrip()}..."


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
