from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.models import (
    ReconstructionJobStatus,
    ReconstructionJobStatusResponse,
    ReconstructionResult,
)


class ReconstructionJobStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

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
            jobs = self._read_jobs()
            jobs[job_id] = job.model_dump(mode="json")
            self._write_jobs(jobs)
        return job

    def get_job(self, job_id: str) -> ReconstructionJobStatusResponse | None:
        with self._lock:
            jobs = self._read_jobs()
            job_data = jobs.get(job_id)
        if not job_data:
            return None
        return self._parse_job(job_data)

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
            jobs = self._read_jobs()
            current = self._require_job(jobs, job_id)
            updates = {
                "status": status,
                "progress": progress,
                "error": error,
            }
            if result is not None:
                updates["result"] = result

            updated = current.model_copy(update=updates)
            jobs[job_id] = updated.model_dump(mode="json")
            self._write_jobs(jobs)
        return updated

    def mark_failed(self, job_id: str, message: str) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.failed,
            progress=100,
            error=message,
        )

    def mark_completed(
        self, job_id: str, result: ReconstructionResult
    ) -> ReconstructionJobStatusResponse:
        return self.update_status(
            job_id,
            status=ReconstructionJobStatus.completed,
            progress=100,
            error=None,
            result=result,
        )

    def _read_jobs(self) -> dict[str, dict]:
        try:
            payload = self.path.read_text(encoding="utf-8")
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _write_jobs(self, jobs: dict[str, dict]) -> None:
        self.path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    @staticmethod
    def _parse_job(job_data: dict) -> ReconstructionJobStatusResponse:
        return ReconstructionJobStatusResponse.model_validate(job_data)

    def _require_job(
        self, jobs: dict[str, dict], job_id: str
    ) -> ReconstructionJobStatusResponse:
        job_data = jobs.get(job_id)
        if not job_data:
            raise KeyError(f"Unknown job_id: {job_id}")
        return self._parse_job(job_data)
