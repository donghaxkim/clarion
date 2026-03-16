from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

from app.config import FIRESTORE_DATABASE, FIRESTORE_PROJECT_ID
from app.models import EvidenceItem as ReportEvidenceItem, EvidenceItemType, GenerateReportRequest, ReportDocument
from app.models.schema import (
    CaseFile,
    Contradiction,
    Entity,
    EvidenceItem as LegacyEvidenceItem,
    MissingInfo,
)
from app.services.cloud.blob_store import BlobStore, GcsBlobStore
from app.services.intelligence.citations import CitationIndex, IndexedFact, build_citation_index
from app.services.intelligence.contradictions import (
    detect_contradictions,
    get_contradictions_for_entity,
)
from app.services.intelligence.missing_info import find_gaps
from app.services.report_bundle_adapter import (
    build_case_evidence_bundle,
    build_report_evidence_item,
    map_legacy_evidence_type,
)

ANALYSIS_STATUS_IDLE = "idle"
ANALYSIS_STATUS_QUEUED = "queued"
ANALYSIS_STATUS_RUNNING = "running"
ANALYSIS_STATUS_COMPLETED = "completed"
ANALYSIS_STATUS_FAILED = "failed"
ANALYSIS_STATUS_STALE = "stale"
ANALYSIS_PENDING_STATUSES = {ANALYSIS_STATUS_QUEUED, ANALYSIS_STATUS_RUNNING}


@dataclass
class CaseWorkspaceRecord:
    case: CaseFile
    description: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    citation_index: CitationIndex | None = None
    pending_videos: list[dict[str, Any]] = field(default_factory=list)
    latest_report_job_id: str | None = None
    latest_report_id: str | None = None
    analysis_status: str = ANALYSIS_STATUS_IDLE
    analysis_error: str | None = None
    analysis_updated_at: datetime | None = None
    evidence_revision: int = 0
    analysis_revision: int = 0
    analysis_target_revision: int = 0


class CaseWorkspaceBackend(Protocol):
    def create_case(
        self,
        *,
        title: str | None = None,
        case_type: str | None = None,
        description: str | None = None,
    ) -> CaseWorkspaceRecord: ...

    def get_case_record(self, case_id: str) -> CaseWorkspaceRecord | None: ...

    def save_case_record(self, record: CaseWorkspaceRecord) -> CaseWorkspaceRecord: ...

    def merge_case_fields(self, case_id: str, updates: dict[str, Any]) -> CaseWorkspaceRecord: ...

    def commit_analysis_result(
        self,
        case_id: str,
        *,
        expected_revision: int,
        contradictions: list[Contradiction],
        missing_info: list[MissingInfo],
        citation_index: CitationIndex,
    ) -> CaseWorkspaceRecord: ...

    def clear(self) -> None: ...

    def count_cases(self) -> int: ...


class CaseWorkspaceService:
    def __init__(
        self,
        *,
        backend: CaseWorkspaceBackend | None = None,
        blob_store: BlobStore | None = None,
    ):
        self._backend = backend or _default_backend(blob_store=blob_store)

    def create_case(
        self,
        *,
        title: str | None = None,
        case_type: str | None = None,
        description: str | None = None,
    ) -> CaseWorkspaceRecord:
        return self._backend.create_case(
            title=title,
            case_type=case_type,
            description=description,
        )

    def get_case_record(self, case_id: str) -> CaseWorkspaceRecord | None:
        return self._backend.get_case_record(case_id)

    def require_case_record(self, case_id: str) -> CaseWorkspaceRecord:
        record = self.get_case_record(case_id)
        if record is None:
            raise KeyError(f"Unknown case_id: {case_id}")
        return record

    def mark_upload_started(self, case_id: str) -> CaseWorkspaceRecord:
        return self._update_status(case_id, "parsing")

    def mark_upload_finished(self, case_id: str) -> CaseWorkspaceRecord:
        current = self.require_case_record(case_id)
        next_status = "intake" if current.case.evidence else "intake"
        return self._update_status(case_id, next_status)

    def add_pending_video(self, case_id: str, pending_video: dict[str, Any]) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        record.pending_videos.append(dict(pending_video))
        record.updated_at = datetime.now(UTC)
        return self._backend.save_case_record(record)

    def attach_evidence(self, case_id: str, evidence: LegacyEvidenceItem) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        record.case.evidence.append(evidence)
        self._merge_entities(record.case, evidence.entities)
        record.case.status = "intake"
        record.updated_at = datetime.now(UTC)
        record.evidence_revision += 1
        record.analysis_error = None
        if record.analysis_revision > 0 or record.analysis_status in ANALYSIS_PENDING_STATUSES:
            record.analysis_status = ANALYSIS_STATUS_STALE
        else:
            record.analysis_status = ANALYSIS_STATUS_IDLE
        record.analysis_target_revision = record.evidence_revision
        return self._backend.save_case_record(record)

    def analyze_case(self, case_id: str) -> CaseWorkspaceRecord:
        return self.run_analysis(case_id)

    def run_analysis(
        self,
        case_id: str,
        *,
        expected_revision: int | None = None,
        force: bool = False,
    ) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        if not record.case.evidence:
            raise ValueError("No evidence uploaded yet")

        target_revision = expected_revision or record.evidence_revision
        if target_revision <= 0:
            raise ValueError("No evidence uploaded yet")

        if expected_revision is not None and record.evidence_revision != expected_revision:
            return record

        if not force and self._analysis_is_current(record, revision=target_revision):
            return record

        running_record = self._mark_analysis_running(case_id, expected_revision=target_revision)
        if running_record.evidence_revision != target_revision:
            return running_record

        working_record = self.require_case_record(case_id)
        if working_record.evidence_revision != target_revision:
            return working_record

        try:
            index = build_citation_index(working_record.case)
            contradictions = detect_contradictions(working_record.case, index)
            missing_info = find_gaps(working_record.case, index)
        except Exception as exc:
            self._mark_analysis_failed(case_id, expected_revision=target_revision, message=str(exc))
            raise

        return self._backend.commit_analysis_result(
            case_id,
            expected_revision=target_revision,
            contradictions=contradictions,
            missing_info=missing_info,
            citation_index=index,
        )

    def queue_analysis_for_current_revision(self, case_id: str) -> tuple[CaseWorkspaceRecord, int, bool]:
        record = self.require_case_record(case_id)
        if not record.case.evidence:
            raise ValueError("No evidence uploaded yet")

        revision = record.evidence_revision
        if self._analysis_is_current(record, revision=revision):
            return record, revision, False
        if (
            record.analysis_status in ANALYSIS_PENDING_STATUSES
            and record.analysis_target_revision == revision
        ):
            return record, revision, False

        queued = self._backend.merge_case_fields(
            case_id,
            {
                "analysis_status": ANALYSIS_STATUS_QUEUED,
                "analysis_error": None,
                "analysis_updated_at": datetime.now(UTC),
                "analysis_target_revision": revision,
            },
        )
        return queued, revision, True

    def mark_analysis_dispatch_failed(
        self,
        case_id: str,
        *,
        expected_revision: int,
        message: str,
    ) -> CaseWorkspaceRecord:
        return self._mark_analysis_failed(
            case_id,
            expected_revision=expected_revision,
            message=message,
        )

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
        if not record.case.evidence:
            raise ValueError("No evidence uploaded yet")
        bundle = build_case_evidence_bundle(
            record.case,
            case_summary=record.description or record.case.intake_summary or record.case.title,
        )
        return GenerateReportRequest(
            bundle=bundle,
            user_id=user_id,
            enable_public_context=enable_public_context,
            max_images=max_images,
            max_reconstructions=max_reconstructions,
        )

    def record_latest_report_refs(
        self,
        case_id: str,
        *,
        report_id: str,
        job_id: str,
    ) -> CaseWorkspaceRecord:
        return self._backend.merge_case_fields(
            case_id,
            {
                "latest_report_id": report_id,
                "latest_report_job_id": job_id,
                "status": "generating",
                "updated_at": datetime.now(UTC),
            },
        )

    def sync_report_status(
        self,
        case_id: str,
        *,
        status: str,
    ) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        next_status = record.case.status
        if status == "completed":
            next_status = "complete"
        elif status == "failed":
            next_status = "analyzed" if self._analysis_is_current(record) else "intake"
        elif status:
            next_status = "generating"
        return self._backend.merge_case_fields(
            case_id,
            {
                "status": next_status,
                "updated_at": datetime.now(UTC),
            },
        )

    def get_entity_payload(self, case_id: str, entity_name: str) -> dict[str, Any]:
        record = self.require_case_record(case_id)
        entity = next(
            (item for item in record.case.entities if item.name.lower() == entity_name.lower()),
            None,
        )
        if entity is None:
            raise KeyError(f"Unknown entity_name: {entity_name}")

        evidence_lookup = _evidence_filename_lookup(record.case)
        has_current_analysis = self._analysis_is_current(record)

        indexed_facts: list[dict[str, Any]] = []
        if has_current_analysis and record.citation_index is not None:
            indexed_facts = [
                {
                    "fact": fact.fact_text,
                    "dimension": fact.dimension,
                    "source": evidence_lookup.get(
                        fact.source_location.evidence_id,
                        fact.source_location.evidence_id,
                    ),
                    "evidence_id": fact.source_location.evidence_id,
                    "page": fact.source_location.page,
                    "timestamp_start": fact.source_location.timestamp_start,
                    "excerpt": fact.excerpt,
                    "reliability": fact.reliability,
                }
                for fact in record.citation_index.query_by_entity(entity_name)
            ]

        contradictions = []
        if has_current_analysis:
            contradictions = [
                _serialize_contradiction(contradiction, evidence_lookup=evidence_lookup)
                for contradiction in get_contradictions_for_entity(record.case.contradictions, entity_name)
            ]

        return {
            "entity": {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "aliases": list(entity.aliases),
            },
            "mentions": [
                {
                    "evidence_id": mention.evidence_id,
                    "source": evidence_lookup.get(mention.evidence_id, mention.evidence_id),
                    "page": mention.page,
                    "timestamp_start": mention.timestamp_start,
                    "excerpt": mention.excerpt,
                }
                for mention in entity.mentions
            ],
            "facts": indexed_facts,
            "contradictions": contradictions,
        }

    def serialize_case(
        self,
        case_id: str,
        *,
        report_store: Any | None = None,
    ) -> dict[str, Any]:
        record = self.require_case_record(case_id)
        report = self._load_latest_report(record, report_store=report_store)
        return _serialize_case_record(record, report=report)

    def clear(self) -> None:
        self._backend.clear()

    def count_cases(self) -> int:
        return self._backend.count_cases()

    def _mark_analysis_running(
        self,
        case_id: str,
        *,
        expected_revision: int,
    ) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        if record.evidence_revision != expected_revision:
            return record

        next_status = record.case.status
        if next_status not in {"generating", "complete"}:
            next_status = "analyzing"

        return self._backend.merge_case_fields(
            case_id,
            {
                "analysis_status": ANALYSIS_STATUS_RUNNING,
                "analysis_error": None,
                "analysis_updated_at": datetime.now(UTC),
                "analysis_target_revision": expected_revision,
                "status": next_status,
            },
        )

    def _mark_analysis_failed(
        self,
        case_id: str,
        *,
        expected_revision: int,
        message: str,
    ) -> CaseWorkspaceRecord:
        record = self.require_case_record(case_id)
        if record.evidence_revision != expected_revision:
            return record

        next_status = record.case.status
        if next_status == "analyzing":
            next_status = "intake"

        return self._backend.merge_case_fields(
            case_id,
            {
                "analysis_status": ANALYSIS_STATUS_FAILED,
                "analysis_error": message,
                "analysis_updated_at": datetime.now(UTC),
                "analysis_target_revision": expected_revision,
                "status": next_status,
            },
        )

    def _update_status(self, case_id: str, status: str) -> CaseWorkspaceRecord:
        return self._backend.merge_case_fields(
            case_id,
            {
                "status": status,
                "updated_at": datetime.now(UTC),
            },
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
        return build_report_evidence_item(item)

    @staticmethod
    def _analysis_is_current(
        record: CaseWorkspaceRecord,
        *,
        revision: int | None = None,
    ) -> bool:
        target_revision = revision or record.evidence_revision
        return (
            target_revision > 0
            and record.analysis_status == ANALYSIS_STATUS_COMPLETED
            and record.analysis_revision == target_revision
            and record.citation_index is not None
        )

    def _load_latest_report(
        self,
        record: CaseWorkspaceRecord,
        *,
        report_store: Any | None = None,
    ) -> ReportDocument | None:
        if not record.latest_report_job_id and not record.latest_report_id:
            return None

        if report_store is None:
            from app.services.generation import ReportJobStore

            report_store = ReportJobStore()

        if record.latest_report_job_id:
            job = report_store.get_job(record.latest_report_job_id)
            if job is not None and job.report is not None:
                return job.report
        if record.latest_report_id:
            return report_store.get_report(record.latest_report_id)
        return None


class InMemoryCaseWorkspaceBackend:
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
            self._cases[case.id] = _copy_record(record)
            return _copy_record(record)

    def get_case_record(self, case_id: str) -> CaseWorkspaceRecord | None:
        with self._lock:
            record = self._cases.get(case_id)
            return None if record is None else _copy_record(record)

    def save_case_record(self, record: CaseWorkspaceRecord) -> CaseWorkspaceRecord:
        with self._lock:
            self._cases[record.case.id] = _copy_record(record)
            return _copy_record(record)

    def merge_case_fields(self, case_id: str, updates: dict[str, Any]) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._cases.get(case_id)
            if record is None:
                raise KeyError(f"Unknown case_id: {case_id}")
            _apply_record_updates(record, updates)
            self._cases[case_id] = _copy_record(record)
            return _copy_record(record)

    def commit_analysis_result(
        self,
        case_id: str,
        *,
        expected_revision: int,
        contradictions: list[Contradiction],
        missing_info: list[MissingInfo],
        citation_index: CitationIndex,
    ) -> CaseWorkspaceRecord:
        with self._lock:
            record = self._cases.get(case_id)
            if record is None:
                raise KeyError(f"Unknown case_id: {case_id}")
            if record.evidence_revision != expected_revision:
                return _copy_record(record)
            record.case.contradictions = contradictions
            record.case.missing_info = missing_info
            record.citation_index = citation_index
            record.analysis_status = ANALYSIS_STATUS_COMPLETED
            record.analysis_error = None
            record.analysis_updated_at = datetime.now(UTC)
            record.analysis_revision = expected_revision
            record.analysis_target_revision = expected_revision
            if record.case.status not in {"generating", "complete"}:
                record.case.status = "analyzed"
            record.updated_at = datetime.now(UTC)
            self._cases[case_id] = _copy_record(record)
            return _copy_record(record)

    def clear(self) -> None:
        with self._lock:
            self._cases.clear()

    def count_cases(self) -> int:
        with self._lock:
            return len(self._cases)


class FirestoreCaseWorkspaceBackend:
    CASES_COLLECTION = "cases"
    EVIDENCE_SUBCOLLECTION = "evidence"

    def __init__(
        self,
        *,
        blob_store: BlobStore,
        client: Any | None = None,
        project_id: str | None = None,
        database: str | None = None,
    ):
        self.blob_store = blob_store
        self._client = client
        self.project_id = (project_id or FIRESTORE_PROJECT_ID).strip() or None
        self.database = (database or FIRESTORE_DATABASE).strip() or "(default)"

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
        self.save_case_record(record)
        return self.get_case_record(case.id) or record

    def get_case_record(self, case_id: str) -> CaseWorkspaceRecord | None:
        client = self._get_client()
        snapshot = self._case_ref(client, case_id).get()
        if not snapshot.exists:
            return None

        doc = snapshot.to_dict() or {}
        evidence_items = self._load_evidence_items(case_id)
        case = CaseFile(
            id=doc.get("case_id", case_id),
            created_at=_parse_datetime(doc.get("created_at")) or datetime.now(UTC),
            title=doc.get("title"),
            case_type=doc.get("case_type"),
            intake_summary=doc.get("description"),
            evidence=evidence_items,
            entities=[Entity.model_validate(item) for item in doc.get("entities", [])],
            contradictions=[
                Contradiction.model_validate(item)
                for item in doc.get("contradictions", [])
            ],
            missing_info=[
                MissingInfo.model_validate(item)
                for item in doc.get("missing_info", [])
            ],
            report_sections=[],
            status=doc.get("status", "intake"),
        )
        return CaseWorkspaceRecord(
            case=case,
            description=doc.get("description"),
            updated_at=_parse_datetime(doc.get("updated_at")) or datetime.now(UTC),
            citation_index=self._load_citation_index(doc.get("citation_index_gcs_uri")),
            pending_videos=[dict(item) for item in doc.get("pending_videos", [])],
            latest_report_job_id=doc.get("latest_report_job_id"),
            latest_report_id=doc.get("latest_report_id"),
            analysis_status=doc.get("analysis_status", ANALYSIS_STATUS_IDLE),
            analysis_error=doc.get("analysis_error"),
            analysis_updated_at=_parse_datetime(doc.get("analysis_updated_at")),
            evidence_revision=int(doc.get("evidence_revision", 0) or 0),
            analysis_revision=int(doc.get("analysis_revision", 0) or 0),
            analysis_target_revision=int(doc.get("analysis_target_revision", 0) or 0),
        )

    def save_case_record(self, record: CaseWorkspaceRecord) -> CaseWorkspaceRecord:
        client = self._get_client()
        citation_index_gcs_uri = None
        if record.citation_index is not None:
            citation_index_gcs_uri = self.blob_store.upload_json(
                _serialize_citation_index(record.citation_index),
                _citation_index_key(record.case.id),
            )

        case_doc = {
            "case_id": record.case.id,
            "title": record.case.title,
            "case_type": record.case.case_type,
            "description": record.description or record.case.intake_summary,
            "status": record.case.status,
            "created_at": record.case.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "entities": [entity.model_dump(mode="json") for entity in record.case.entities],
            "contradictions": [
                contradiction.model_dump(mode="json") for contradiction in record.case.contradictions
            ],
            "missing_info": [item.model_dump(mode="json") for item in record.case.missing_info],
            "pending_videos": [dict(item) for item in record.pending_videos],
            "latest_report_job_id": record.latest_report_job_id,
            "latest_report_id": record.latest_report_id,
            "citation_index_gcs_uri": citation_index_gcs_uri,
            "analysis_status": record.analysis_status,
            "analysis_error": record.analysis_error,
            "analysis_updated_at": _serialize_datetime(record.analysis_updated_at),
            "evidence_revision": record.evidence_revision,
            "analysis_revision": record.analysis_revision,
            "analysis_target_revision": record.analysis_target_revision,
        }
        self._case_ref(client, record.case.id).set(case_doc)

        for evidence in record.case.evidence:
            self._save_evidence_item(record.case.id, evidence)

        return self.get_case_record(record.case.id) or record

    def merge_case_fields(self, case_id: str, updates: dict[str, Any]) -> CaseWorkspaceRecord:
        client = self._get_client()
        self._case_ref(client, case_id).set(
            _serialize_case_field_updates(updates),
            merge=True,
        )
        record = self.get_case_record(case_id)
        if record is None:
            raise KeyError(f"Unknown case_id: {case_id}")
        return record

    def commit_analysis_result(
        self,
        case_id: str,
        *,
        expected_revision: int,
        contradictions: list[Contradiction],
        missing_info: list[MissingInfo],
        citation_index: CitationIndex,
    ) -> CaseWorkspaceRecord:
        client = self._get_client()
        case_ref = self._case_ref(client, case_id)
        citation_index_gcs_uri = self.blob_store.upload_json(
            _serialize_citation_index(citation_index),
            _citation_index_key(case_id),
        )

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for case workspace persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        transaction = client.transaction()

        @firestore.transactional
        def _commit(transaction):
            snapshot = case_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise KeyError(f"Unknown case_id: {case_id}")
            doc = snapshot.to_dict() or {}
            if int(doc.get("evidence_revision", 0) or 0) != expected_revision:
                return False

            current_status = doc.get("status", "intake")
            if current_status not in {"generating", "complete"}:
                current_status = "analyzed"

            transaction.set(
                case_ref,
                {
                    "contradictions": [
                        contradiction.model_dump(mode="json")
                        for contradiction in contradictions
                    ],
                    "missing_info": [item.model_dump(mode="json") for item in missing_info],
                    "citation_index_gcs_uri": citation_index_gcs_uri,
                    "analysis_status": ANALYSIS_STATUS_COMPLETED,
                    "analysis_error": None,
                    "analysis_updated_at": datetime.now(UTC).isoformat(),
                    "analysis_revision": expected_revision,
                    "analysis_target_revision": expected_revision,
                    "status": current_status,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                merge=True,
            )
            return True

        _commit(transaction)
        record = self.get_case_record(case_id)
        if record is None:
            raise KeyError(f"Unknown case_id: {case_id}")
        return record

    def clear(self) -> None:
        client = self._get_client()
        for snapshot in self._cases_collection(client).stream():
            case_ref = self._case_ref(client, snapshot.id)
            for evidence_snapshot in case_ref.collection(self.EVIDENCE_SUBCOLLECTION).stream():
                evidence_snapshot.reference.delete()
            case_ref.delete()

    def count_cases(self) -> int:
        client = self._get_client()
        return sum(1 for _ in self._cases_collection(client).stream())

    def _load_evidence_items(self, case_id: str) -> list[LegacyEvidenceItem]:
        client = self._get_client()
        evidence_ref = self._case_ref(client, case_id).collection(self.EVIDENCE_SUBCOLLECTION)
        snapshots = list(evidence_ref.stream())
        snapshots.sort(
            key=lambda snapshot: (
                (snapshot.to_dict() or {}).get("uploaded_at") or "",
                snapshot.id,
            )
        )
        evidence_items: list[LegacyEvidenceItem] = []
        for snapshot in snapshots:
            doc = snapshot.to_dict() or {}
            parsed_gcs_uri = doc.get("parsed_gcs_uri")
            if parsed_gcs_uri:
                evidence_items.append(_deserialize_evidence(self.blob_store.download_json(parsed_gcs_uri)))
                continue
            evidence_items.append(
                LegacyEvidenceItem(
                    id=doc["evidence_id"],
                    filename=doc["filename"],
                    evidence_type=doc["evidence_type"],
                    media={
                        "url": doc["media_url"],
                        "media_type": doc.get("media_type", "application/octet-stream"),
                    },
                    content={"text": doc.get("content_text")},
                    entities=[Entity.model_validate(item) for item in doc.get("entities_payload", [])],
                    labels=list(doc.get("labels", [])),
                    summary=doc.get("summary"),
                    uploaded_at=_parse_datetime(doc.get("uploaded_at")) or datetime.now(UTC),
                )
            )
        return evidence_items

    def _save_evidence_item(self, case_id: str, evidence: LegacyEvidenceItem) -> None:
        client = self._get_client()
        parsed_gcs_uri = self.blob_store.upload_json(
            _serialize_evidence(evidence),
            _parsed_evidence_key(case_id, evidence.id),
        )
        payload = {
            "evidence_id": evidence.id,
            "filename": evidence.filename,
            "evidence_type": getattr(evidence.evidence_type, "value", evidence.evidence_type),
            "labels": list(evidence.labels),
            "summary": evidence.summary,
            "entity_count": len(evidence.entities),
            "entities": [
                {"type": entity.type, "name": entity.name}
                for entity in evidence.entities
            ],
            "entities_payload": [entity.model_dump(mode="json") for entity in evidence.entities],
            "status": "parsed",
            "media_url": evidence.media.url,
            "media_type": evidence.media.media_type,
            "uploaded_at": evidence.uploaded_at.isoformat(),
            "content_text": evidence.content.text,
            "parsed_gcs_uri": parsed_gcs_uri,
        }
        self._case_ref(client, case_id).collection(self.EVIDENCE_SUBCOLLECTION).document(
            evidence.id
        ).set(payload)

    def _load_citation_index(self, citation_index_gcs_uri: str | None) -> CitationIndex | None:
        if not citation_index_gcs_uri:
            return None
        return _deserialize_citation_index(self.blob_store.download_json(citation_index_gcs_uri))

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for case workspace persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        kwargs: dict[str, Any] = {}
        if self.project_id:
            kwargs["project"] = self.project_id
        if self.database and self.database != "(default)":
            kwargs["database"] = self.database

        try:
            self._client = firestore.Client(**kwargs)
        except TypeError:
            kwargs.pop("database", None)
            self._client = firestore.Client(**kwargs)
        return self._client

    @classmethod
    def _cases_collection(cls, client: Any):
        return client.collection(cls.CASES_COLLECTION)

    @classmethod
    def _case_ref(cls, client: Any, case_id: str):
        return cls._cases_collection(client).document(case_id)


def _default_backend(*, blob_store: BlobStore | None = None) -> CaseWorkspaceBackend:
    project_id = FIRESTORE_PROJECT_ID.strip()
    if project_id:
        try:
            from google.cloud import firestore  # type: ignore # noqa: F401
        except Exception:
            return InMemoryCaseWorkspaceBackend()
        return FirestoreCaseWorkspaceBackend(blob_store=blob_store or GcsBlobStore())
    return InMemoryCaseWorkspaceBackend()


def _copy_record(record: CaseWorkspaceRecord) -> CaseWorkspaceRecord:
    return CaseWorkspaceRecord(
        case=record.case.model_copy(deep=True),
        description=record.description,
        updated_at=record.updated_at,
        citation_index=_deserialize_citation_index(_serialize_citation_index(record.citation_index))
        if record.citation_index is not None
        else None,
        pending_videos=[dict(item) for item in record.pending_videos],
        latest_report_job_id=record.latest_report_job_id,
        latest_report_id=record.latest_report_id,
        analysis_status=record.analysis_status,
        analysis_error=record.analysis_error,
        analysis_updated_at=record.analysis_updated_at,
        evidence_revision=record.evidence_revision,
        analysis_revision=record.analysis_revision,
        analysis_target_revision=record.analysis_target_revision,
    )


def _serialize_case_record(
    record: CaseWorkspaceRecord,
    *,
    report: ReportDocument | None = None,
) -> dict[str, Any]:
    case = record.case
    evidence_lookup = _evidence_filename_lookup(case)
    has_current_analysis = _analysis_is_current(record)
    contradictions = (
        [
            _serialize_contradiction(contradiction, evidence_lookup=evidence_lookup)
            for contradiction in case.contradictions
        ]
        if has_current_analysis
        else []
    )
    missing_info = (
        [_serialize_missing_info(item) for item in case.missing_info]
        if has_current_analysis
        else []
    )
    return {
        "case_id": case.id,
        "title": case.title,
        "case_type": case.case_type,
        "description": record.description or case.intake_summary,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "latest_report_job_id": record.latest_report_job_id,
        "latest_report_id": record.latest_report_id,
        "analysis_status": record.analysis_status,
        "analysis_error": record.analysis_error,
        "analysis_updated_at": _serialize_datetime(record.analysis_updated_at),
        "evidence_revision": record.evidence_revision,
        "analysis_revision": record.analysis_revision,
        "evidence": [
            {
                "evidence_id": evidence.id,
                "filename": evidence.filename,
                "evidence_type": getattr(evidence.evidence_type, "value", evidence.evidence_type),
                "labels": list(evidence.labels),
                "summary": evidence.summary,
                "entity_count": len(evidence.entities),
                "entities": [
                    {"type": entity.type, "name": entity.name}
                    for entity in evidence.entities
                ],
                "status": "parsed",
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
        "report_relevant_entities": _serialize_entities(
            _relevant_entities_for_report(record, report=report)
        ),
        "contradictions": contradictions,
        "missing_info": missing_info,
        "pending_videos": [dict(item) for item in record.pending_videos],
    }


def _serialize_entities(entities: list[Entity]) -> list[dict[str, Any]]:
    return [
        {
            "id": entity.id,
            "type": entity.type,
            "name": entity.name,
            "aliases": list(entity.aliases),
            "mention_count": len(entity.mentions),
        }
        for entity in entities
    ]


def _relevant_entities_for_report(
    record: CaseWorkspaceRecord,
    *,
    report: ReportDocument | None,
) -> list[Entity]:
    if report is None:
        return []

    cited_evidence_ids = {
        citation.source_id
        for block in report.sections
        for citation in block.citations
        if citation.source_id
    }
    if not cited_evidence_ids:
        return []

    relevant_entity_ids = {
        entity.id
        for entity in record.case.entities
        if any(mention.evidence_id in cited_evidence_ids for mention in entity.mentions)
    }

    if _analysis_is_current(record) and record.citation_index is not None:
        related_names = {
            _normalize_entity_name(name)
            for fact in record.citation_index.facts
            if fact.source_location.evidence_id in cited_evidence_ids
            for name in fact.related_entities
        }
        relevant_entity_ids.update(
            entity.id
            for entity in record.case.entities
            if _normalize_entity_name(entity.name) in related_names
        )
        relevant_entity_ids.update(
            entity.id
            for entity in record.case.entities
            if any(
                contradiction.source_a.evidence_id in cited_evidence_ids
                or contradiction.source_b.evidence_id in cited_evidence_ids
                for contradiction in get_contradictions_for_entity(
                    record.case.contradictions,
                    entity.name,
                )
            )
        )

    return [
        entity
        for entity in record.case.entities
        if entity.id in relevant_entity_ids
    ]


def _normalize_entity_name(value: str) -> str:
    return value.strip().lower()


def _analysis_is_current(record: CaseWorkspaceRecord) -> bool:
    return (
        record.evidence_revision > 0
        and record.analysis_status == ANALYSIS_STATUS_COMPLETED
        and record.analysis_revision == record.evidence_revision
        and record.citation_index is not None
    )


def _evidence_filename_lookup(case: CaseFile) -> dict[str, str]:
    return {evidence.id: evidence.filename for evidence in case.evidence}


def _serialize_contradiction(
    contradiction: Contradiction,
    *,
    evidence_lookup: dict[str, str],
) -> dict[str, Any]:
    source_a = evidence_lookup.get(contradiction.source_a.evidence_id, contradiction.source_a.detail)
    source_b = evidence_lookup.get(contradiction.source_b.evidence_id, contradiction.source_b.detail)
    return {
        "id": contradiction.id,
        "severity": _normalize_contradiction_severity(
            getattr(contradiction.severity, "value", contradiction.severity)
        ),
        "description": contradiction.description,
        "fact_a": {
            "text": contradiction.fact_a,
            "source": source_a,
            "evidence_id": contradiction.source_a.evidence_id,
        },
        "fact_b": {
            "text": contradiction.fact_b,
            "source": source_b,
            "evidence_id": contradiction.source_b.evidence_id,
        },
    }


def _serialize_missing_info(item: MissingInfo) -> dict[str, Any]:
    severity = getattr(item.severity, "value", item.severity)
    normalized = {
        "critical": "high",
        "warning": "medium",
        "suggestion": "low",
    }.get(str(severity), "low")
    return {
        "id": item.id,
        "severity": normalized,
        "description": item.description,
        "recommendation": item.recommendation,
    }


def _normalize_contradiction_severity(value: Any) -> str:
    normalized = str(value)
    if normalized == "critical":
        return "high"
    return normalized


def _serialize_evidence(evidence: LegacyEvidenceItem) -> dict[str, Any]:
    return {
        "evidence": evidence.model_dump(mode="json"),
        "analysis": getattr(evidence, "_analysis", None),
    }


def _deserialize_evidence(payload: dict[str, Any]) -> LegacyEvidenceItem:
    evidence = LegacyEvidenceItem.model_validate(payload.get("evidence", payload))
    analysis = payload.get("analysis")
    if analysis is not None:
        evidence._analysis = analysis
    return evidence


def _serialize_citation_index(index: CitationIndex | None) -> dict[str, Any]:
    if index is None:
        return {}
    return {
        "case_type": index.case_type,
        "dimensions": list(index.dimensions),
        "reliability_map": {
            str(getattr(key, "value", key)): value
            for key, value in index.reliability_map.items()
        },
        "facts": [
            {
                "fact_id": fact.fact_id,
                "fact_text": fact.fact_text,
                "dimension": fact.dimension,
                "related_entities": list(fact.related_entities),
                "source_location": fact.source_location.model_dump(mode="json"),
                "evidence_type": str(getattr(fact.evidence_type, "value", fact.evidence_type)),
                "category": fact.category,
                "excerpt": fact.excerpt,
                "reliability": fact.reliability,
            }
            for fact in index.facts
        ],
    }


def _deserialize_citation_index(payload: dict[str, Any]) -> CitationIndex:
    from app.models.schema import SourceLocation

    index = CitationIndex()
    index.case_type = payload.get("case_type", "unknown")
    index.dimensions = list(payload.get("dimensions", []))
    index.reliability_map = dict(payload.get("reliability_map", {}))
    for item in payload.get("facts", []):
        fact = IndexedFact(
            fact_id=item["fact_id"],
            fact_text=item["fact_text"],
            dimension=item["dimension"],
            related_entities=list(item.get("related_entities", [])),
            source_location=SourceLocation.model_validate(item["source_location"]),
            evidence_type=item.get("evidence_type", EvidenceItemType.other.value),
            category=item.get("category", "other"),
            excerpt=item.get("excerpt", ""),
            reliability=float(item.get("reliability", 0.0)),
        )
        index.add_fact(fact)
    return index


def _serialize_case_field_updates(updates: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in updates.items():
        if key in {"updated_at", "analysis_updated_at"}:
            serialized[key] = _serialize_datetime(value)
        else:
            serialized[key] = value
    return serialized


def _apply_record_updates(record: CaseWorkspaceRecord, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if key == "status":
            record.case.status = str(value)
        elif key == "updated_at":
            record.updated_at = value
        elif key == "latest_report_job_id":
            record.latest_report_job_id = value
        elif key == "latest_report_id":
            record.latest_report_id = value
        elif key == "analysis_status":
            record.analysis_status = str(value)
        elif key == "analysis_error":
            record.analysis_error = None if value is None else str(value)
        elif key == "analysis_updated_at":
            record.analysis_updated_at = value
        elif key == "evidence_revision":
            record.evidence_revision = int(value)
        elif key == "analysis_revision":
            record.analysis_revision = int(value)
        elif key == "analysis_target_revision":
            record.analysis_target_revision = int(value)


def _parsed_evidence_key(case_id: str, evidence_id: str) -> str:
    return f"cases/{case_id}/parsed/{evidence_id}.json"


def _citation_index_key(case_id: str) -> str:
    return f"cases/{case_id}/analysis/citation_index.json"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _map_legacy_evidence_type(evidence_type: Any) -> EvidenceItemType:
    return map_legacy_evidence_type(evidence_type)


case_workspace_service = CaseWorkspaceService()
