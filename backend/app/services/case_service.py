from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.models import (
    CaseEvidenceBundle,
    EntityMention,
    EvidenceItem as ReportEvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
)
from app.models.schema import (
    CaseFile,
    Contradiction,
    Entity,
    EvidenceItem as LegacyEvidenceItem,
)
from app.services.intelligence.citations import CitationIndex, build_citation_index
from app.services.intelligence.contradictions import (
    detect_contradictions,
    get_contradictions_for_entity,
)


@dataclass
class CaseWorkspaceRecord:
    case: CaseFile
    description: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    citation_index: CitationIndex | None = None
    pending_videos: list[dict[str, Any]] = field(default_factory=list)


class CaseWorkspaceService:
    def __init__(self):
        self._lock = Lock()
        self._cases: dict[str, CaseWorkspaceRecord] = {}

    def create_case(
        self,
        *,
        title: str | None = None,
        case_type: str | None = None,
        description: str | None = None,
    ) -> CaseWorkspaceRecord:
        case = CaseFile(
            title=title,
            case_type=case_type,
            intake_summary=description,
            status="intake",
        )
        record = CaseWorkspaceRecord(case=case, description=description)
        with self._lock:
            self._cases[case.id] = record
        return self.get_case_record(case.id) or record

    def get_case_record(self, case_id: str) -> CaseWorkspaceRecord | None:
        with self._lock:
            record = self._cases.get(case_id)
            if record is None:
                return None
            return self._copy_record(record)

    def require_case_record(self, case_id: str) -> CaseWorkspaceRecord:
        record = self.get_case_record(case_id)
        if record is None:
            raise KeyError(f"Unknown case_id: {case_id}")
        return record

    def mark_upload_started(self, case_id: str) -> CaseWorkspaceRecord:
        return self._update_status(case_id, "parsing")

    def mark_upload_finished(self, case_id: str) -> CaseWorkspaceRecord:
        return self._update_status(case_id, "intake")

    def add_pending_video(self, case_id: str, pending_video: dict[str, Any]) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._require_mutable_record(case_id)
            record.pending_videos.append(dict(pending_video))
            record.updated_at = datetime.now(UTC)
            return self._copy_record(record)

    def attach_evidence(self, case_id: str, evidence: LegacyEvidenceItem) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._require_mutable_record(case_id)
            record.case.evidence.append(evidence)
            self._merge_entities(record.case, evidence.entities)
            record.updated_at = datetime.now(UTC)
            return self._copy_record(record)

    def analyze_case(self, case_id: str) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._require_mutable_record(case_id)
            if not record.case.evidence:
                raise ValueError("No evidence uploaded yet")
            record.case.status = "analyzing"
            record.updated_at = datetime.now(UTC)

        index = build_citation_index(self.require_case_record(case_id).case)
        contradictions = detect_contradictions(self.require_case_record(case_id).case, index)

        with self._lock:
            record = self._require_mutable_record(case_id)
            record.citation_index = index
            record.case.contradictions = contradictions
            record.case.status = "analyzed"
            record.updated_at = datetime.now(UTC)
            return self._copy_record(record)

    def build_generate_request(
        self,
        case_id: str,
        *,
        user_id: str = "clarion-user",
        enable_public_context: bool | None = None,
        max_images: int | None = None,
        max_reconstructions: int | None = None,
    ) -> GenerateReportRequest:
        record = self.require_case_record(case_id)
        bundle = CaseEvidenceBundle(
            case_id=record.case.id,
            case_summary=record.description or record.case.intake_summary or record.case.title,
            evidence_items=[
                self._to_report_evidence_item(item)
                for item in record.case.evidence
            ],
            entities=[
                EntityMention(
                    entity_id=entity.id,
                    name=entity.name,
                    role=entity.type,
                )
                for entity in record.case.entities
            ],
        )
        return GenerateReportRequest(
            bundle=bundle,
            user_id=user_id,
            enable_public_context=enable_public_context,
            max_images=max_images,
            max_reconstructions=max_reconstructions,
        )

    def get_entity_payload(self, case_id: str, entity_name: str) -> dict[str, Any]:
        record = self.require_case_record(case_id)
        entity = next(
            (item for item in record.case.entities if item.name.lower() == entity_name.lower()),
            None,
        )
        if entity is None:
            raise KeyError(f"Unknown entity_name: {entity_name}")

        indexed_facts: list[dict[str, Any]] = []
        if record.citation_index is not None:
            indexed_facts = [
                {
                    "fact": fact.fact_text,
                    "dimension": fact.dimension,
                    "source_evidence_id": fact.source_location.evidence_id,
                    "page": fact.source_location.page,
                    "excerpt": fact.excerpt,
                    "reliability": fact.reliability,
                }
                for fact in record.citation_index.query_by_entity(entity_name)
            ]

        contradictions = [
            {
                "id": contradiction.id,
                "severity": getattr(contradiction.severity, "value", contradiction.severity),
                "description": contradiction.description,
                "fact_a": contradiction.fact_a,
                "fact_b": contradiction.fact_b,
            }
            for contradiction in get_contradictions_for_entity(record.case.contradictions, entity_name)
        ]

        return {
            "entity": {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "aliases": list(entity.aliases),
                "mentions": [
                    {
                        "evidence_id": mention.evidence_id,
                        "page": mention.page,
                        "timestamp_start": mention.timestamp_start,
                        "excerpt": mention.excerpt,
                    }
                    for mention in entity.mentions
                ],
            },
            "facts": indexed_facts,
            "contradictions": contradictions,
        }

    def serialize_case(self, case_id: str) -> dict[str, Any]:
        record = self.require_case_record(case_id)
        return _serialize_case_record(record)

    def clear(self) -> None:
        with self._lock:
            self._cases.clear()

    def count_cases(self) -> int:
        with self._lock:
            return len(self._cases)

    def _update_status(self, case_id: str, status: str) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._require_mutable_record(case_id)
            record.case.status = status
            record.updated_at = datetime.now(UTC)
            return self._copy_record(record)

    def _require_mutable_record(self, case_id: str) -> CaseWorkspaceRecord:
        record = self._cases.get(case_id)
        if record is None:
            raise KeyError(f"Unknown case_id: {case_id}")
        return record

    def _copy_record(self, record: CaseWorkspaceRecord) -> CaseWorkspaceRecord:
        return CaseWorkspaceRecord(
            case=record.case.model_copy(deep=True),
            description=record.description,
            updated_at=record.updated_at,
            citation_index=record.citation_index,
            pending_videos=[dict(item) for item in record.pending_videos],
        )

    @staticmethod
    def _merge_entities(case: CaseFile, entities: list[Entity]) -> None:
        for entity in entities:
            existing = next(
                (item for item in case.entities if item.name.lower() == entity.name.lower()),
                None,
            )
            if existing is None:
                case.entities.append(entity)
                continue
            existing.mentions.extend(entity.mentions)
            existing.aliases = list(dict.fromkeys([*existing.aliases, *entity.aliases]))

    @staticmethod
    def _to_report_evidence_item(item: LegacyEvidenceItem) -> ReportEvidenceItem:
        extracted_text = item.content.text
        return ReportEvidenceItem(
            evidence_id=item.id,
            kind=_map_legacy_evidence_type(item.evidence_type),
            title=item.filename,
            summary=item.summary,
            extracted_text=extracted_text,
            media_uri=item.media.url,
            source_uri=item.media.url,
        )


def _serialize_case_record(record: CaseWorkspaceRecord) -> dict[str, Any]:
    case = record.case
    return {
        "case_id": case.id,
        "title": case.title,
        "case_type": case.case_type,
        "description": record.description or case.intake_summary,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "evidence": [
            {
                "id": evidence.id,
                "filename": evidence.filename,
                "evidence_type": getattr(evidence.evidence_type, "value", evidence.evidence_type),
                "labels": list(evidence.labels),
                "summary": evidence.summary,
                "entity_count": len(evidence.entities),
            }
            for evidence in case.evidence
        ],
        "entities": [
            {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "aliases": list(entity.aliases),
                "mention_count": len(entity.mentions),
            }
            for entity in case.entities
        ],
        "contradictions": [
            _serialize_contradiction(contradiction)
            for contradiction in case.contradictions
        ],
        "pending_videos": [dict(item) for item in record.pending_videos],
    }


def _serialize_contradiction(contradiction: Contradiction) -> dict[str, Any]:
    return {
        "id": contradiction.id,
        "severity": getattr(contradiction.severity, "value", contradiction.severity),
        "description": contradiction.description,
        "fact_a": contradiction.fact_a,
        "fact_b": contradiction.fact_b,
    }


def _map_legacy_evidence_type(evidence_type: Any) -> EvidenceItemType:
    value = getattr(evidence_type, "value", evidence_type)
    mapping = {
        "police_report": EvidenceItemType.official_record,
        "medical_record": EvidenceItemType.medical,
        "witness_statement": EvidenceItemType.transcript,
        "photo": EvidenceItemType.image,
        "dashcam_video": EvidenceItemType.video,
        "surveillance_video": EvidenceItemType.video,
        "insurance_document": EvidenceItemType.official_record,
        "diagram": EvidenceItemType.image,
        "other": EvidenceItemType.other,
    }
    return mapping.get(str(value), EvidenceItemType.other)


case_workspace_service = CaseWorkspaceService()
