from __future__ import annotations

from app.models import GenerateReportRequest, ReportDocument
from app.models.report_schema import Citation as ReportCitation
from app.models.schema import CaseFile
from app.services.case_service import CaseWorkspaceRecord, CaseWorkspaceService, case_workspace_service
from app.services.generation.job_store import ReportJobStore
from app.services.intelligence.contradictions import get_contradictions_for_entity
from app.services.voice.models import (
    VoiceContradiction,
    VoiceEntity,
    VoiceEntityFact,
    VoiceEvidence,
    VoiceMention,
    VoiceMissingInfo,
    VoiceReportSection,
    VoiceSectionCitation,
    VoiceSessionContext,
)


class VoiceContextService:
    def __init__(
        self,
        *,
        report_store: ReportJobStore | None = None,
        case_service: CaseWorkspaceService | None = None,
    ):
        self.report_store = report_store or ReportJobStore()
        self.case_service = case_service or case_workspace_service

    def get_context(
        self,
        report_id: str,
        *,
        focused_section_id: str | None = None,
    ) -> VoiceSessionContext | None:
        report = self.report_store.get_report(report_id)
        if report is None:
            return None

        request = self.report_store.get_request_for_report(report_id)
        case_id = request.bundle.case_id if request is not None else None
        record = self.case_service.get_case_record(case_id) if case_id else None
        case = record.case if record is not None else None
        analysis_current = _has_current_analysis(record)

        sections = _build_sections(report)
        return VoiceSessionContext(
            report_id=report_id,
            case_id=case_id,
            title=_resolve_title(report_id, report, request, case),
            case_type=_resolve_case_type(request, case),
            status=_stringify_status(report.status),
            evidence=_build_evidence(request, case),
            entities=_build_entities(request, case, record=record, analysis_current=analysis_current),
            contradictions=_build_contradictions(case, analysis_current=analysis_current),
            missing_info=_build_missing_info(case, analysis_current=analysis_current),
            sections=sections,
            focused_section=next(
                (section for section in sections if section.section_id == focused_section_id),
                None,
            ),
        )


def _resolve_title(
    report_id: str,
    report: ReportDocument,
    request: GenerateReportRequest | None,
    case: CaseFile | None,
) -> str:
    if case is not None and case.title:
        return case.title
    if request is not None and request.bundle.case_summary:
        return request.bundle.case_summary
    for section in report.sections:
        if section.title:
            return section.title
    return f"Report {report_id}"


def _resolve_case_type(
    request: GenerateReportRequest | None,
    case: CaseFile | None,
) -> str | None:
    if case is not None and case.case_type:
        return case.case_type
    return None if request is None else None


def _build_evidence(
    request: GenerateReportRequest | None,
    case: CaseFile | None,
) -> list[VoiceEvidence]:
    if case is not None and case.evidence:
        return [
            VoiceEvidence(
                evidence_id=evidence.id,
                filename=evidence.filename,
                evidence_type=str(getattr(evidence.evidence_type, "value", evidence.evidence_type)),
                summary=evidence.summary,
                content_text=evidence.content.text,
                media_url=evidence.media.url,
            )
            for evidence in case.evidence
        ]

    if request is None:
        return []

    return [
        VoiceEvidence(
            evidence_id=evidence.evidence_id,
            filename=evidence.title or evidence.evidence_id,
            evidence_type=str(getattr(evidence.kind, "value", evidence.kind)),
            summary=evidence.summary,
            content_text=evidence.extracted_text,
            media_url=evidence.media_uri or evidence.source_uri,
        )
        for evidence in request.bundle.evidence_items
    ]


def _build_entities(
    request: GenerateReportRequest | None,
    case: CaseFile | None,
    *,
    record: CaseWorkspaceRecord | None,
    analysis_current: bool,
) -> list[VoiceEntity]:
    if case is not None and case.entities:
        evidence_lookup = {evidence.id: evidence.filename for evidence in case.evidence}
        entities: list[VoiceEntity] = []
        for entity in case.entities:
            facts = _build_entity_facts(
                entity_name=entity.name,
                record=record,
                evidence_lookup=evidence_lookup,
                analysis_current=analysis_current,
            )
            contradictions = _build_entity_contradictions(
                entity_name=entity.name,
                case=case,
                analysis_current=analysis_current,
            )
            entities.append(
                VoiceEntity(
                    entity_id=entity.id,
                    entity_type=entity.type,
                    name=entity.name,
                    aliases=list(entity.aliases),
                    mentions=[
                        VoiceMention(
                            evidence_id=mention.evidence_id,
                            source=evidence_lookup.get(mention.evidence_id, mention.evidence_id),
                            page=mention.page,
                            timestamp_start=mention.timestamp_start,
                            excerpt=mention.excerpt,
                        )
                        for mention in entity.mentions
                    ],
                    facts=facts,
                    contradictions=contradictions,
                )
            )
        return entities

    if request is None:
        return []

    return [
        VoiceEntity(
            entity_id=entity.entity_id,
            entity_type=entity.role or "entity",
            name=entity.name,
        )
        for entity in request.bundle.entities
    ]


def _build_entity_facts(
    *,
    entity_name: str,
    record: CaseWorkspaceRecord | None,
    evidence_lookup: dict[str, str],
    analysis_current: bool,
) -> list[VoiceEntityFact]:
    if not analysis_current or record is None or record.citation_index is None:
        return []
    return [
        VoiceEntityFact(
            fact=fact.fact_text,
            dimension=fact.dimension,
            source=evidence_lookup.get(fact.source_location.evidence_id, fact.source_location.evidence_id),
            evidence_id=fact.source_location.evidence_id,
            page=fact.source_location.page,
            timestamp_start=fact.source_location.timestamp_start,
            excerpt=fact.excerpt,
            reliability=fact.reliability,
        )
        for fact in record.citation_index.query_by_entity(entity_name)
    ]


def _build_entity_contradictions(
    *,
    entity_name: str,
    case: CaseFile,
    analysis_current: bool,
) -> list[VoiceContradiction]:
    if not analysis_current:
        return []
    return [
        VoiceContradiction(
            contradiction_id=contradiction.id,
            severity=str(getattr(contradiction.severity, "value", contradiction.severity)),
            description=contradiction.description,
            fact_a=contradiction.fact_a,
            fact_b=contradiction.fact_b,
        )
        for contradiction in get_contradictions_for_entity(case.contradictions, entity_name)
    ]


def _build_contradictions(
    case: CaseFile | None,
    *,
    analysis_current: bool,
) -> list[VoiceContradiction]:
    if case is None or not analysis_current:
        return []
    return [
        VoiceContradiction(
            contradiction_id=contradiction.id,
            severity=str(getattr(contradiction.severity, "value", contradiction.severity)),
            description=contradiction.description,
            fact_a=contradiction.fact_a,
            fact_b=contradiction.fact_b,
        )
        for contradiction in case.contradictions
    ]


def _build_missing_info(
    case: CaseFile | None,
    *,
    analysis_current: bool,
) -> list[VoiceMissingInfo]:
    if case is None or not analysis_current:
        return []
    return [
        VoiceMissingInfo(
            item_id=item.id,
            severity=str(getattr(item.severity, "value", item.severity)),
            description=item.description,
            recommendation=item.recommendation,
        )
        for item in case.missing_info
    ]


def _build_sections(report: ReportDocument) -> list[VoiceReportSection]:
    sections: list[VoiceReportSection] = []
    for block in sorted(report.sections, key=lambda item: item.sort_key):
        citations = _build_citations(block.citations)
        if block.title:
            sections.append(
                VoiceReportSection(
                    section_id=f"{block.id}--heading",
                    canonical_block_id=block.id,
                    kind="heading",
                    edit_target="title",
                    title=block.title,
                    text=block.title,
                    citations=citations,
                )
            )
        sections.append(
            VoiceReportSection(
                section_id=block.id,
                canonical_block_id=block.id,
                kind=str(getattr(block.type, "value", block.type)),
                edit_target="content" if str(getattr(block.type, "value", block.type)) == "text" else ("title" if block.title else "content"),
                title=block.title,
                text=block.content or block.title,
                citations=citations,
            )
        )
    return sections


def _build_citations(citations: list[ReportCitation]) -> list[VoiceSectionCitation]:
    built: list[VoiceSectionCitation] = []
    for citation in citations:
        if not citation.source_label or not citation.excerpt:
            continue
        built.append(
            VoiceSectionCitation(
                source_id=citation.source_id,
                source_label=citation.source_label,
                excerpt=citation.excerpt,
                provenance=str(getattr(citation.provenance, "value", citation.provenance)),
                uri=citation.uri,
            )
        )
    return built


def _has_current_analysis(record: CaseWorkspaceRecord | None) -> bool:
    if record is None:
        return False
    return (
        record.evidence_revision > 0
        and record.analysis_status == "completed"
        and record.analysis_revision == record.evidence_revision
        and record.citation_index is not None
    )


def _stringify_status(status: object) -> str:
    return str(getattr(status, "value", status))


voice_context_service = VoiceContextService()
