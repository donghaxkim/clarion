from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from app.config import FIRESTORE_DATABASE, FIRESTORE_PROJECT_ID
from app.models import (
    GenerateReportRequest,
    ReportArtifactRefs,
    ReportDocument,
    ReportGenerationActivity,
    ReportGenerationJobRecord,
    ReportGenerationJobStatus,
    ReportGenerationJobStatusResponse,
    ReportJobEvent,
    ReportStatus,
    ReportWorkflowState,
)
from app.services.cloud.blob_store import BlobStore, GcsBlobStore, InMemoryBlobStore


class ReportJobBackend(Protocol):
    def create_job(
        self,
        *,
        report: ReportDocument,
        activity: ReportGenerationActivity | None,
        workflow: ReportWorkflowState | None,
    ) -> ReportGenerationJobRecord: ...

    def get_job(self, job_id: str) -> ReportGenerationJobRecord | None: ...

    def get_status(self, job_id: str) -> ReportGenerationJobStatusResponse | None: ...

    def get_report(self, report_id: str) -> ReportDocument | None: ...

    def get_request_for_report(self, report_id: str) -> GenerateReportRequest | None: ...

    def get_events_since(self, job_id: str, event_id: int) -> list[ReportJobEvent]: ...

    def publish(
        self,
        job_id: str,
        *,
        event_type: str,
        payload: dict,
        status: ReportGenerationJobStatus | None = None,
        progress: int | None = None,
        warning: str | None = None,
        error: str | None = None,
        report: ReportDocument | None = None,
        artifacts: ReportArtifactRefs | None = None,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
    ) -> ReportGenerationJobRecord: ...

    def mark_completed(
        self,
        job_id: str,
        *,
        report: ReportDocument,
        artifacts: ReportArtifactRefs | None,
    ) -> ReportGenerationJobRecord: ...

    def mark_failed(self, job_id: str, message: str) -> ReportGenerationJobRecord: ...

    def save_request(self, job_id: str, payload: GenerateReportRequest) -> str: ...

    def load_request(self, job_id: str) -> GenerateReportRequest: ...

    def claim_job(self, job_id: str) -> bool: ...


class ReportJobStore:
    def __init__(
        self,
        path: str | None = None,
        *,
        backend: ReportJobBackend | None = None,
        blob_store: BlobStore | None = None,
    ):
        # `path` is retained for backward-compatible construction in tests and old call sites.
        self.path = path
        self._backend = backend
        self._blob_store = blob_store
        if self._backend is None and path is not None:
            memory_blob_store = self._blob_store or InMemoryBlobStore()
            self._blob_store = memory_blob_store
            self._backend = InMemoryReportJobBackend(blob_store=memory_blob_store)

    def create_job(
        self,
        *,
        report: ReportDocument,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
    ) -> ReportGenerationJobRecord:
        return self._get_backend().create_job(
            report=report,
            activity=activity,
            workflow=workflow,
        )

    def get_job(self, job_id: str) -> ReportGenerationJobRecord | None:
        return self._get_backend().get_job(job_id)

    def get_status(self, job_id: str) -> ReportGenerationJobStatusResponse | None:
        return self._get_backend().get_status(job_id)

    def get_report(self, report_id: str) -> ReportDocument | None:
        return self._get_backend().get_report(report_id)

    def get_request_for_report(self, report_id: str) -> GenerateReportRequest | None:
        return self._get_backend().get_request_for_report(report_id)

    def get_events_since(self, job_id: str, event_id: int) -> list[ReportJobEvent]:
        return self._get_backend().get_events_since(job_id, event_id)

    def publish(
        self,
        job_id: str,
        *,
        event_type: str,
        payload: dict,
        status: ReportGenerationJobStatus | None = None,
        progress: int | None = None,
        warning: str | None = None,
        error: str | None = None,
        report: ReportDocument | None = None,
        artifacts: ReportArtifactRefs | None = None,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
    ) -> ReportGenerationJobRecord:
        return self._get_backend().publish(
            job_id,
            event_type=event_type,
            payload=payload,
            status=status,
            progress=progress,
            warning=warning,
            error=error,
            report=report,
            artifacts=artifacts,
            activity=activity,
            workflow=workflow,
        )

    def mark_completed(
        self,
        job_id: str,
        *,
        report: ReportDocument,
        artifacts: ReportArtifactRefs | None,
    ) -> ReportGenerationJobRecord:
        return self._get_backend().mark_completed(
            job_id,
            report=report,
            artifacts=artifacts,
        )

    def mark_failed(self, job_id: str, message: str) -> ReportGenerationJobRecord:
        return self._get_backend().mark_failed(job_id, message)

    def save_request(self, job_id: str, payload: GenerateReportRequest) -> str:
        return self._get_backend().save_request(job_id, payload)

    def load_request(self, job_id: str) -> GenerateReportRequest:
        return self._get_backend().load_request(job_id)

    def claim_job(self, job_id: str) -> bool:
        return self._get_backend().claim_job(job_id)

    def _get_backend(self) -> ReportJobBackend:
        if self._backend is None:
            self._backend = FirestoreReportJobBackend(
                blob_store=self._blob_store or GcsBlobStore()
            )
        return self._backend


class FirestoreReportJobBackend:
    JOBS_COLLECTION = "report_jobs"
    REPORTS_COLLECTION = "reports"
    EVENTS_SUBCOLLECTION = "events"

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

    def create_job(
        self,
        *,
        report: ReportDocument,
        activity: ReportGenerationActivity | None,
        workflow: ReportWorkflowState | None,
    ) -> ReportGenerationJobRecord:
        job = ReportGenerationJobRecord(
            job_id=str(uuid.uuid4()),
            report_id=report.report_id,
            status=ReportGenerationJobStatus.queued,
            progress=0,
            warnings=[],
            error=None,
            report=report,
            artifacts=None,
            activity=activity,
            workflow=workflow,
            events=[],
        )
        report_gcs_uri = self._persist_preview_report(job.job_id, report)
        job_doc = _job_doc_from_record(job, report_gcs_uri=report_gcs_uri, next_event_id=0)

        client = self._get_client()
        self._job_ref(client, job.job_id).set(job_doc)
        self._report_ref(client, report.report_id).set(
            _report_metadata_doc(
                report_id=report.report_id,
                status=report.status,
                report_gcs_uri=report_gcs_uri,
                job_id=job.job_id,
            )
        )
        return job

    def get_job(self, job_id: str) -> ReportGenerationJobRecord | None:
        client = self._get_client()
        snapshot = self._job_ref(client, job_id).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        return self._hydrate_job_record(job_id, doc)

    def get_status(self, job_id: str) -> ReportGenerationJobStatusResponse | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        return ReportGenerationJobStatusResponse.model_validate(job.model_dump(mode="json"))

    def get_report(self, report_id: str) -> ReportDocument | None:
        client = self._get_client()
        snapshot = self._report_ref(client, report_id).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        report_gcs_uri = doc.get("report_gcs_uri")
        if not report_gcs_uri:
            return None
        return self._load_report(report_gcs_uri)

    def get_request_for_report(self, report_id: str) -> GenerateReportRequest | None:
        client = self._get_client()
        snapshot = self._report_ref(client, report_id).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        job_id = doc.get("job_id")
        if not job_id:
            return None
        try:
            return self.load_request(job_id)
        except Exception:
            return None

    def get_events_since(self, job_id: str, event_id: int) -> list[ReportJobEvent]:
        client = self._get_client()
        query = (
            self._job_ref(client, job_id)
            .collection(self.EVENTS_SUBCOLLECTION)
            .order_by("event_id")
        )
        if event_id >= 0:
            query = query.where("event_id", ">", event_id)
        return [
            ReportJobEvent.model_validate(snapshot.to_dict() or {})
            for snapshot in query.stream()
        ]

    def publish(
        self,
        job_id: str,
        *,
        event_type: str,
        payload: dict,
        status: ReportGenerationJobStatus | None = None,
        progress: int | None = None,
        warning: str | None = None,
        error: str | None = None,
        report: ReportDocument | None = None,
        artifacts: ReportArtifactRefs | None = None,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
    ) -> ReportGenerationJobRecord:
        client = self._get_client()
        job_ref = self._job_ref(client, job_id)
        report_gcs_uri = None
        if artifacts is not None and artifacts.report_gcs_uri:
            report_gcs_uri = artifacts.report_gcs_uri
        elif report is not None:
            report_gcs_uri = self._persist_preview_report(job_id, report)

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for report job persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        transaction = client.transaction()

        @firestore.transactional
        def _write(transaction):
            snapshot = job_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise KeyError(f"Unknown job_id: {job_id}")
            current_doc = snapshot.to_dict() or {}
            current_job = _job_status_from_doc(current_doc)

            warnings = list(current_job.warnings)
            if warning and warning not in warnings:
                warnings.append(warning)

            event_id = int(current_doc.get("next_event_id", 0))
            event = ReportJobEvent(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )

            next_updates = {
                "warnings": warnings,
                "error": error,
                "artifacts": artifacts or current_job.artifacts,
                "activity": activity or current_job.activity,
                "workflow": workflow or current_job.workflow,
            }
            if status is not None:
                next_updates["status"] = status
            resolved_progress = _resolve_progress(
                current_progress=current_job.progress,
                next_progress=progress,
                next_status=status,
            )
            if resolved_progress is not None:
                next_updates["progress"] = resolved_progress

            updated = current_job.model_copy(update=next_updates)
            next_doc = dict(current_doc)
            next_doc.update(
                _job_doc_from_status(
                    updated,
                    report_gcs_uri=report_gcs_uri or current_doc.get("report_gcs_uri"),
                    next_event_id=event_id + 1,
                )
            )

            transaction.set(job_ref, next_doc)
            transaction.set(
                job_ref.collection(self.EVENTS_SUBCOLLECTION).document(f"{event_id:08d}"),
                event.model_dump(mode="json"),
            )

            if report_gcs_uri:
                report_status = report.status if report is not None else ReportStatus.running
                transaction.set(
                    self._report_ref(client, updated.report_id),
                    _report_metadata_doc(
                        report_id=updated.report_id,
                        status=report_status,
                        report_gcs_uri=report_gcs_uri,
                        job_id=job_id,
                    ),
                )

        _write(transaction)
        updated = self.get_job(job_id)
        if updated is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return updated

    def mark_completed(
        self,
        job_id: str,
        *,
        report: ReportDocument,
        artifacts: ReportArtifactRefs | None,
    ) -> ReportGenerationJobRecord:
        return self.publish(
            job_id,
            event_type="job.completed",
            payload={"report_id": report.report_id},
            status=ReportGenerationJobStatus.completed,
            progress=100,
            report=report,
            artifacts=artifacts,
        )

    def mark_failed(self, job_id: str, message: str) -> ReportGenerationJobRecord:
        job = self.get_job(job_id)
        failed_report = None
        if job is not None and job.report is not None:
            failed_report = job.report.model_copy(update={"status": ReportStatus.failed})
        return self.publish(
            job_id,
            event_type="job.failed",
            payload={"error": message},
            status=ReportGenerationJobStatus.failed,
            error=message,
            report=failed_report,
        )

    def save_request(self, job_id: str, payload: GenerateReportRequest) -> str:
        request_gcs_uri = self.blob_store.upload_json(
            payload.model_dump(mode="json"),
            _report_request_key(job_id),
        )
        client = self._get_client()
        self._job_ref(client, job_id).set(
            {"request_gcs_uri": request_gcs_uri},
            merge=True,
        )
        return request_gcs_uri

    def load_request(self, job_id: str) -> GenerateReportRequest:
        client = self._get_client()
        snapshot = self._job_ref(client, job_id).get()
        if not snapshot.exists:
            raise KeyError(f"Unknown job_id: {job_id}")
        doc = snapshot.to_dict() or {}
        request_gcs_uri = doc.get("request_gcs_uri")
        if not request_gcs_uri:
            raise RuntimeError(f"Missing request payload for report job {job_id}")
        return GenerateReportRequest.model_validate(
            self.blob_store.download_json(request_gcs_uri)
        )

    def claim_job(self, job_id: str) -> bool:
        client = self._get_client()
        job_ref = self._job_ref(client, job_id)

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for report job persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        transaction = client.transaction()

        @firestore.transactional
        def _claim(transaction):
            snapshot = job_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            doc = snapshot.to_dict() or {}
            if doc.get("status") != ReportGenerationJobStatus.queued.value:
                return False
            if doc.get("claimed_at"):
                return False
            next_doc = dict(doc)
            next_doc["claimed_at"] = datetime.now(UTC).isoformat()
            transaction.set(job_ref, next_doc)
            return True

        return bool(_claim(transaction))

    def _hydrate_job_record(self, job_id: str, doc: dict[str, Any]) -> ReportGenerationJobRecord:
        report_gcs_uri = doc.get("report_gcs_uri")
        report = self._load_report(report_gcs_uri) if report_gcs_uri else None
        events = self.get_events_since(job_id, -1)
        payload = _job_status_from_doc(doc).model_dump(mode="json")
        payload["report"] = report.model_dump(mode="json") if report is not None else None
        payload["events"] = [event.model_dump(mode="json") for event in events]
        return ReportGenerationJobRecord.model_validate(payload)

    def _load_report(self, report_gcs_uri: str) -> ReportDocument:
        return ReportDocument.model_validate(self.blob_store.download_json(report_gcs_uri))

    def _persist_preview_report(self, job_id: str, report: ReportDocument) -> str:
        return self.blob_store.upload_json(
            report.model_dump(mode="json"),
            _report_preview_key(job_id),
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for report job persistence. "
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
    def _job_ref(cls, client: Any, job_id: str):
        return client.collection(cls.JOBS_COLLECTION).document(job_id)

    @classmethod
    def _report_ref(cls, client: Any, report_id: str):
        return client.collection(cls.REPORTS_COLLECTION).document(report_id)


class InMemoryReportJobBackend:
    def __init__(self, *, blob_store: BlobStore):
        self.blob_store = blob_store
        self._lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.reports: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}

    def create_job(
        self,
        *,
        report: ReportDocument,
        activity: ReportGenerationActivity | None,
        workflow: ReportWorkflowState | None,
    ) -> ReportGenerationJobRecord:
        job = ReportGenerationJobRecord(
            job_id=str(uuid.uuid4()),
            report_id=report.report_id,
            status=ReportGenerationJobStatus.queued,
            progress=0,
            warnings=[],
            error=None,
            report=report,
            artifacts=None,
            activity=activity,
            workflow=workflow,
            events=[],
        )
        report_gcs_uri = self.blob_store.upload_json(
            report.model_dump(mode="json"),
            _report_preview_key(job.job_id),
        )
        with self._lock:
            self.jobs[job.job_id] = _job_doc_from_record(job, report_gcs_uri=report_gcs_uri, next_event_id=0)
            self.reports[report.report_id] = _report_metadata_doc(
                report_id=report.report_id,
                status=report.status,
                report_gcs_uri=report_gcs_uri,
                job_id=job.job_id,
            )
            self.events[job.job_id] = []
        return job

    def get_job(self, job_id: str) -> ReportGenerationJobRecord | None:
        with self._lock:
            doc = dict(self.jobs.get(job_id) or {})
            events = [dict(event) for event in self.events.get(job_id, [])]
        if not doc:
            return None
        payload = _job_status_from_doc(doc).model_dump(mode="json")
        report_gcs_uri = doc.get("report_gcs_uri")
        report = (
            ReportDocument.model_validate(self.blob_store.download_json(report_gcs_uri))
            if report_gcs_uri
            else None
        )
        payload["report"] = report.model_dump(mode="json") if report is not None else None
        payload["events"] = events
        return ReportGenerationJobRecord.model_validate(payload)

    def get_status(self, job_id: str) -> ReportGenerationJobStatusResponse | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        return ReportGenerationJobStatusResponse.model_validate(job.model_dump(mode="json"))

    def get_report(self, report_id: str) -> ReportDocument | None:
        with self._lock:
            doc = dict(self.reports.get(report_id) or {})
        if not doc:
            return None
        report_gcs_uri = doc.get("report_gcs_uri")
        if not report_gcs_uri:
            return None
        return ReportDocument.model_validate(self.blob_store.download_json(report_gcs_uri))

    def get_request_for_report(self, report_id: str) -> GenerateReportRequest | None:
        with self._lock:
            report_doc = dict(self.reports.get(report_id) or {})
        if not report_doc:
            return None
        job_id = report_doc.get("job_id")
        if not job_id:
            return None
        try:
            return self.load_request(job_id)
        except Exception:
            return None

    def get_events_since(self, job_id: str, event_id: int) -> list[ReportJobEvent]:
        with self._lock:
            items = [dict(event) for event in self.events.get(job_id, [])]
        return [
            ReportJobEvent.model_validate(item)
            for item in items
            if int(item["event_id"]) > event_id
        ]

    def publish(
        self,
        job_id: str,
        *,
        event_type: str,
        payload: dict,
        status: ReportGenerationJobStatus | None = None,
        progress: int | None = None,
        warning: str | None = None,
        error: str | None = None,
        report: ReportDocument | None = None,
        artifacts: ReportArtifactRefs | None = None,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
    ) -> ReportGenerationJobRecord:
        with self._lock:
            current_doc = self.jobs.get(job_id)
            if not current_doc:
                raise KeyError(f"Unknown job_id: {job_id}")
            current_job = _job_status_from_doc(current_doc)

            warnings = list(current_job.warnings)
            if warning and warning not in warnings:
                warnings.append(warning)

            next_updates = {
                "warnings": warnings,
                "error": error,
                "artifacts": artifacts or current_job.artifacts,
                "activity": activity or current_job.activity,
                "workflow": workflow or current_job.workflow,
            }
            if status is not None:
                next_updates["status"] = status
            resolved_progress = _resolve_progress(
                current_progress=current_job.progress,
                next_progress=progress,
                next_status=status,
            )
            if resolved_progress is not None:
                next_updates["progress"] = resolved_progress

            updated = current_job.model_copy(update=next_updates)
            event_id = int(current_doc.get("next_event_id", 0))
            event = ReportJobEvent(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )

            resolved_report_gcs_uri = current_doc.get("report_gcs_uri")
            if artifacts is not None and artifacts.report_gcs_uri and report is not None:
                resolved_report_gcs_uri = _store_json_at_uri(
                    self.blob_store,
                    artifacts.report_gcs_uri,
                    report.model_dump(mode="json"),
                )
            elif artifacts is not None and artifacts.report_gcs_uri:
                resolved_report_gcs_uri = artifacts.report_gcs_uri
            elif report is not None:
                resolved_report_gcs_uri = self.blob_store.upload_json(
                    report.model_dump(mode="json"),
                    _report_preview_key(job_id),
                )

            next_doc = dict(current_doc)
            next_doc.update(
                _job_doc_from_status(
                    updated,
                    report_gcs_uri=resolved_report_gcs_uri,
                    next_event_id=event_id + 1,
                )
            )
            self.jobs[job_id] = next_doc
            self.events.setdefault(job_id, []).append(event.model_dump(mode="json"))

            if resolved_report_gcs_uri:
                report_status = report.status if report is not None else ReportStatus.running
                self.reports[updated.report_id] = _report_metadata_doc(
                    report_id=updated.report_id,
                    status=report_status,
                    report_gcs_uri=resolved_report_gcs_uri,
                    job_id=job_id,
                )

        updated_job = self.get_job(job_id)
        if updated_job is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return updated_job

    def mark_completed(
        self,
        job_id: str,
        *,
        report: ReportDocument,
        artifacts: ReportArtifactRefs | None,
    ) -> ReportGenerationJobRecord:
        return self.publish(
            job_id,
            event_type="job.completed",
            payload={"report_id": report.report_id},
            status=ReportGenerationJobStatus.completed,
            progress=100,
            report=report,
            artifacts=artifacts,
        )

    def mark_failed(self, job_id: str, message: str) -> ReportGenerationJobRecord:
        job = self.get_job(job_id)
        failed_report = None
        if job is not None and job.report is not None:
            failed_report = job.report.model_copy(update={"status": ReportStatus.failed})
        return self.publish(
            job_id,
            event_type="job.failed",
            payload={"error": message},
            status=ReportGenerationJobStatus.failed,
            error=message,
            report=failed_report,
        )

    def save_request(self, job_id: str, payload: GenerateReportRequest) -> str:
        request_gcs_uri = self.blob_store.upload_json(
            payload.model_dump(mode="json"),
            _report_request_key(job_id),
        )
        with self._lock:
            if job_id not in self.jobs:
                raise KeyError(f"Unknown job_id: {job_id}")
            self.jobs[job_id]["request_gcs_uri"] = request_gcs_uri
        return request_gcs_uri

    def load_request(self, job_id: str) -> GenerateReportRequest:
        with self._lock:
            doc = dict(self.jobs.get(job_id) or {})
        if not doc:
            raise KeyError(f"Unknown job_id: {job_id}")
        request_gcs_uri = doc.get("request_gcs_uri")
        if not request_gcs_uri:
            raise RuntimeError(f"Missing request payload for report job {job_id}")
        return GenerateReportRequest.model_validate(
            self.blob_store.download_json(request_gcs_uri)
        )

    def claim_job(self, job_id: str) -> bool:
        with self._lock:
            doc = self.jobs.get(job_id)
            if not doc:
                return False
            if doc.get("status") != ReportGenerationJobStatus.queued.value:
                return False
            if doc.get("claimed_at"):
                return False
            doc["claimed_at"] = datetime.now(UTC).isoformat()
            return True


def _job_doc_from_record(
    job: ReportGenerationJobRecord,
    *,
    report_gcs_uri: str | None,
    next_event_id: int,
) -> dict[str, Any]:
    payload = job.model_dump(mode="json")
    payload.pop("report", None)
    payload.pop("events", None)
    payload["report_gcs_uri"] = report_gcs_uri
    payload["next_event_id"] = next_event_id
    return payload


def _job_doc_from_status(
    job: ReportGenerationJobStatusResponse,
    *,
    report_gcs_uri: str | None,
    next_event_id: int,
) -> dict[str, Any]:
    payload = job.model_dump(mode="json")
    payload.pop("report", None)
    payload["report_gcs_uri"] = report_gcs_uri
    payload["next_event_id"] = next_event_id
    return payload


def _job_status_from_doc(doc: dict[str, Any]) -> ReportGenerationJobStatusResponse:
    payload = dict(doc)
    payload.pop("report_gcs_uri", None)
    payload.pop("next_event_id", None)
    payload.pop("request_gcs_uri", None)
    payload.pop("claimed_at", None)
    return ReportGenerationJobStatusResponse.model_validate(payload)


def _report_metadata_doc(
    *,
    report_id: str,
    status: ReportStatus,
    report_gcs_uri: str,
    job_id: str,
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "status": status.value,
        "report_gcs_uri": report_gcs_uri,
        "job_id": job_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _report_preview_key(job_id: str) -> str:
    return f"report-jobs/{job_id}/report.json"


def _report_request_key(job_id: str) -> str:
    return f"report-jobs/{job_id}/request.json"


def _store_json_at_uri(
    blob_store: BlobStore,
    gcs_uri: str,
    payload: dict[str, Any],
) -> str:
    if hasattr(blob_store, "objects"):
        blob_store.objects[gcs_uri] = {
            "data": json.dumps(payload, indent=2).encode("utf-8"),
            "content_type": "application/json",
        }
        return gcs_uri
    return blob_store.upload_json(payload, _gcs_key_from_uri(gcs_uri))


def _gcs_key_from_uri(gcs_uri: str) -> str:
    body = gcs_uri.removeprefix("gs://")
    _bucket, _, key = body.partition("/")
    if not key:
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    return key


def _resolve_progress(
    *,
    current_progress: int,
    next_progress: int | None,
    next_status: ReportGenerationJobStatus | None,
) -> int | None:
    if next_status == ReportGenerationJobStatus.completed:
        return 100
    if next_status == ReportGenerationJobStatus.failed:
        return current_progress
    if next_progress is None:
        return None
    return max(current_progress, next_progress)
