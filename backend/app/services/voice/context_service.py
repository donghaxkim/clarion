from __future__ import annotations

from app.models import GenerateReportRequest, ReportDocument
from app.models.schema import CaseFile
from app.services.case_service import CaseWorkspaceService, case_workspace_service
from app.services.generation.job_store import ReportJobStore
from app.services.voice.models import (
    VoiceContradiction,
    VoiceEntity,
    VoiceEvidence,
    VoiceMention,
    VoiceReportSection,
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

    def get_context(self, report_id: str) -> VoiceSessionContext | None:
        report = self.report_store.get_report(report_id)
        if report is None:
            return None

        request = self.report_store.get_request_for_report(report_id)
        case_id = request.bundle.case_id if request is not None else None
        record = self.case_service.get_case_record(case_id) if case_id else None
        case = record.case if record is not None else None

        return VoiceSessionContext(
            report_id=report_id,
            case_id=case_id,
            title=_resolve_title(report_id, report, request, case),
            case_type=_resolve_case_type(request, case),
            status=_stringify_status(report.status),
            evidence=_build_evidence(request, case),
            entities=_build_entities(request, case),
            contradictions=_build_contradictions(case),
            sections=_build_sections(report),
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
) -> list[VoiceEntity]:
    if case is not None and case.entities:
        return [
            VoiceEntity(
                entity_id=entity.id,
                entity_type=entity.type,
                name=entity.name,
                aliases=list(entity.aliases),
                mentions=[
                    VoiceMention(
                        evidence_id=mention.evidence_id,
                        page=mention.page,
                        timestamp_start=mention.timestamp_start,
                        excerpt=mention.excerpt,
                    )
                    for mention in entity.mentions
                ],
            )
            for entity in case.entities
        ]

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


def _build_contradictions(case: CaseFile | None) -> list[VoiceContradiction]:
    if case is None:
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


def _build_sections(report: ReportDocument) -> list[VoiceReportSection]:
    return [
        VoiceReportSection(
            section_id=section.id,
            kind=str(getattr(section.type, "value", section.type)),
            title=section.title,
            text=section.content,
        )
        for section in report.sections
    ]


def _stringify_status(status: object) -> str:
    return str(getattr(status, "value", status))


voice_context_service = VoiceContextService()
