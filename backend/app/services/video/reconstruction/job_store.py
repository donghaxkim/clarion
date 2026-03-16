from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from app.config import FIRESTORE_DATABASE, FIRESTORE_PROJECT_ID
from app.models import (
    ReconstructionJobRequest,
    ReconstructionJobStatus,
    ReconstructionJobStatusResponse,
    ReconstructionResult,
)
from app.services.cloud.blob_store import BlobStore, GcsBlobStore, InMemoryBlobStore


class ReconstructionJobBackend(Protocol):
    def create_job(self) -> ReconstructionJobStatusResponse: ...

    def get_job(self, job_id: str) -> ReconstructionJobStatusResponse | None: ...

    def update_status(
        self,
        job_id: str,
        *,
        status: ReconstructionJobStatus,
        progress: int,
        error: str | None = None,
        result: ReconstructionResult | None = None,
    ) -> ReconstructionJobStatusResponse: ...

    def mark_failed(self, job_id: str, message: str) -> ReconstructionJobStatusResponse: ...

    def mark_completed(
        self,
        job_id: str,
        result: ReconstructionResult,
    ) -> ReconstructionJobStatusResponse: ...

    def save_request(self, job_id: str, payload: ReconstructionJobRequest) -> str: ...

    def load_request(self, job_id: str) -> ReconstructionJobRequest: ...

    def claim_job(self, job_id: str) -> bool: ...


class ReconstructionJobStore:
    def __init__(
        self,
        path: str | None = None,
        *,
        backend: ReconstructionJobBackend | None = None,
        blob_store: BlobStore | None = None,
    ):
        # `path` is retained for backward-compatible construction in tests and old call sites.
        self.path = path
        self._backend = backend
        self._blob_store = blob_store
        if self._backend is None and path is not None:
            memory_blob_store = self._blob_store or InMemoryBlobStore()
            self._blob_store = memory_blob_store
            self._backend = InMemoryReconstructionJobBackend(blob_store=memory_blob_store)

    def create_job(self) -> ReconstructionJobStatusResponse:
        return self._get_backend().create_job()

    def get_job(self, job_id: str) -> ReconstructionJobStatusResponse | None:
        return self._get_backend().get_job(job_id)

    def update_status(
        self,
        job_id: str,
        *,
        status: ReconstructionJobStatus,
        progress: int,
        error: str | None = None,
        result: ReconstructionResult | None = None,
    ) -> ReconstructionJobStatusResponse:
        return self._get_backend().update_status(
            job_id,
            status=status,
            progress=progress,
            error=error,
            result=result,
        )

    def mark_failed(self, job_id: str, message: str) -> ReconstructionJobStatusResponse:
        return self._get_backend().mark_failed(job_id, message)

    def mark_completed(
        self,
        job_id: str,
        result: ReconstructionResult,
    ) -> ReconstructionJobStatusResponse:
        return self._get_backend().mark_completed(job_id, result)

    def save_request(self, job_id: str, payload: ReconstructionJobRequest) -> str:
        return self._get_backend().save_request(job_id, payload)

    def load_request(self, job_id: str) -> ReconstructionJobRequest:
        return self._get_backend().load_request(job_id)

    def claim_job(self, job_id: str) -> bool:
        return self._get_backend().claim_job(job_id)

    def _get_backend(self) -> ReconstructionJobBackend:
        if self._backend is None:
            self._backend = FirestoreReconstructionJobBackend(
                blob_store=self._blob_store or GcsBlobStore()
            )
        return self._backend


class FirestoreReconstructionJobBackend:
    COLLECTION = "reconstruction_jobs"

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

    def create_job(self) -> ReconstructionJobStatusResponse:
        job_id = str(uuid.uuid4())
        job = ReconstructionJobStatusResponse(
            job_id=job_id,
            status=ReconstructionJobStatus.queued,
            progress=0,
            error=None,
            result=None,
        )
        self._job_ref(self._get_client(), job_id).set(job.model_dump(mode="json"))
        return job

    def get_job(self, job_id: str) -> ReconstructionJobStatusResponse | None:
        snapshot = self._job_ref(self._get_client(), job_id).get()
        if not snapshot.exists:
            return None
        return _job_from_doc(snapshot.to_dict() or {})

    def update_status(
        self,
        job_id: str,
        *,
        status: ReconstructionJobStatus,
        progress: int,
        error: str | None = None,
        result: ReconstructionResult | None = None,
    ) -> ReconstructionJobStatusResponse:
        client = self._get_client()
        job_ref = self._job_ref(client, job_id)

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for reconstruction job persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        transaction = client.transaction()

        @firestore.transactional
        def _write(transaction):
            snapshot = job_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise KeyError(f"Unknown job_id: {job_id}")
            current = _job_from_doc(snapshot.to_dict() or {})
            updates = {
                "status": status,
                "progress": progress,
                "error": error,
            }
            if result is not None:
                updates["result"] = result

            updated = current.model_copy(update=updates)
            next_doc = dict(snapshot.to_dict() or {})
            next_doc.update(updated.model_dump(mode="json"))
            transaction.set(job_ref, next_doc)

        _write(transaction)
        updated = self.get_job(job_id)
        if updated is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return updated

    def mark_failed(self, job_id: str, message: str) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.failed,
            progress=100,
            error=message,
        )

    def mark_completed(
        self,
        job_id: str,
        result: ReconstructionResult,
    ) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.completed,
            progress=100,
            error=None,
            result=result,
        )

    def save_request(self, job_id: str, payload: ReconstructionJobRequest) -> str:
        request_gcs_uri = self.blob_store.upload_json(
            payload.model_dump(mode="json"),
            _reconstruction_request_key(job_id),
        )
        self._job_ref(self._get_client(), job_id).set(
            {"request_gcs_uri": request_gcs_uri},
            merge=True,
        )
        return request_gcs_uri

    def load_request(self, job_id: str) -> ReconstructionJobRequest:
        snapshot = self._job_ref(self._get_client(), job_id).get()
        if not snapshot.exists:
            raise KeyError(f"Unknown job_id: {job_id}")
        doc = snapshot.to_dict() or {}
        request_gcs_uri = doc.get("request_gcs_uri")
        if not request_gcs_uri:
            raise RuntimeError(f"Missing request payload for reconstruction job {job_id}")
        return ReconstructionJobRequest.model_validate(
            self.blob_store.download_json(request_gcs_uri)
        )

    def claim_job(self, job_id: str) -> bool:
        client = self._get_client()
        job_ref = self._job_ref(client, job_id)

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for reconstruction job persistence. "
                "Install `google-cloud-firestore`."
            ) from exc

        transaction = client.transaction()

        @firestore.transactional
        def _claim(transaction):
            snapshot = job_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            doc = snapshot.to_dict() or {}
            if doc.get("status") != ReconstructionJobStatus.queued.value:
                return False
            if doc.get("claimed_at"):
                return False
            next_doc = dict(doc)
            next_doc["claimed_at"] = datetime.now(UTC).isoformat()
            transaction.set(job_ref, next_doc)
            return True

        return bool(_claim(transaction))

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import firestore  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-firestore is required for reconstruction job persistence. "
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
        return client.collection(cls.COLLECTION).document(job_id)


class InMemoryReconstructionJobBackend:
    def __init__(self, *, blob_store: BlobStore):
        self.blob_store = blob_store
        self._lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}

    def create_job(self) -> ReconstructionJobStatusResponse:
        job_id = str(uuid.uuid4())
        job = ReconstructionJobStatusResponse(
            job_id=job_id,
            status=ReconstructionJobStatus.queued,
            progress=0,
            error=None,
            result=None,
        )
        with self._lock:
            self.jobs[job_id] = job.model_dump(mode="json")
        return job

    def get_job(self, job_id: str) -> ReconstructionJobStatusResponse | None:
        with self._lock:
            job_data = dict(self.jobs.get(job_id) or {})
        if not job_data:
            return None
        return _job_from_doc(job_data)

    def update_status(
        self,
        job_id: str,
        *,
        status: ReconstructionJobStatus,
        progress: int,
        error: str | None = None,
        result: ReconstructionResult | None = None,
    ) -> ReconstructionJobStatusResponse:
        with self._lock:
            current = self.jobs.get(job_id)
            if not current:
                raise KeyError(f"Unknown job_id: {job_id}")
            current_job = _job_from_doc(current)
            updates = {
                "status": status,
                "progress": progress,
                "error": error,
            }
            if result is not None:
                updates["result"] = result
            updated = current_job.model_copy(update=updates)
            next_doc = dict(current)
            next_doc.update(updated.model_dump(mode="json"))
            self.jobs[job_id] = next_doc
        refreshed = self.get_job(job_id)
        if refreshed is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return refreshed

    def mark_failed(self, job_id: str, message: str) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.failed,
            progress=100,
            error=message,
        )

    def mark_completed(
        self,
        job_id: str,
        result: ReconstructionResult,
    ) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.completed,
            progress=100,
            error=None,
            result=result,
        )

    def save_request(self, job_id: str, payload: ReconstructionJobRequest) -> str:
        request_gcs_uri = self.blob_store.upload_json(
            payload.model_dump(mode="json"),
            _reconstruction_request_key(job_id),
        )
        with self._lock:
            if job_id not in self.jobs:
                raise KeyError(f"Unknown job_id: {job_id}")
            self.jobs[job_id]["request_gcs_uri"] = request_gcs_uri
        return request_gcs_uri

    def load_request(self, job_id: str) -> ReconstructionJobRequest:
        with self._lock:
            job_data = dict(self.jobs.get(job_id) or {})
        if not job_data:
            raise KeyError(f"Unknown job_id: {job_id}")
        request_gcs_uri = job_data.get("request_gcs_uri")
        if not request_gcs_uri:
            raise RuntimeError(f"Missing request payload for reconstruction job {job_id}")
        return ReconstructionJobRequest.model_validate(
            self.blob_store.download_json(request_gcs_uri)
        )

    def claim_job(self, job_id: str) -> bool:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            if job.get("status") != ReconstructionJobStatus.queued.value:
                return False
            if job.get("claimed_at"):
                return False
            job["claimed_at"] = datetime.now(UTC).isoformat()
            return True


def _job_from_doc(job_data: dict[str, Any]) -> ReconstructionJobStatusResponse:
    payload = dict(job_data)
    payload.pop("request_gcs_uri", None)
    payload.pop("claimed_at", None)
    return ReconstructionJobStatusResponse.model_validate(payload)


def _reconstruction_request_key(job_id: str) -> str:
    return f"reconstruction-jobs/{job_id}/request.json"
