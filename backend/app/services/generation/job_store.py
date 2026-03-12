from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models import (
    ReportGenerationActivity,
    ReportArtifactRefs,
    ReportDocument,
    ReportGenerationJobRecord,
    ReportGenerationJobStatus,
    ReportGenerationJobStatusResponse,
    ReportJobEvent,
    ReportStatus,
    ReportWorkflowState,
)


class ReportJobStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_payload({"jobs": {}, "reports": {}})

    def create_job(
        self,
        *,
        report: ReportDocument,
        activity: ReportGenerationActivity | None = None,
        workflow: ReportWorkflowState | None = None,
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
        with self._lock:
            payload = self._read_payload()
            payload["jobs"][job.job_id] = job.model_dump(mode="json")
            payload["reports"][report.report_id] = report.model_dump(mode="json")
            self._write_payload(payload)
        return job

    def get_job(self, job_id: str) -> ReportGenerationJobRecord | None:
        with self._lock:
            payload = self._read_payload()
            job_data = payload["jobs"].get(job_id)
        if not job_data:
            return None
        return ReportGenerationJobRecord.model_validate(job_data)

    def get_status(self, job_id: str) -> ReportGenerationJobStatusResponse | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        return ReportGenerationJobStatusResponse.model_validate(job.model_dump(mode="json"))

    def get_report(self, report_id: str) -> ReportDocument | None:
        with self._lock:
            payload = self._read_payload()
            report_data = payload["reports"].get(report_id)
        if not report_data:
            return None
        return ReportDocument.model_validate(report_data)

    def get_events_since(self, job_id: str, event_id: int) -> list[ReportJobEvent]:
        job = self.get_job(job_id)
        if job is None:
            return []
        return [event for event in job.events if event.event_id > event_id]

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
            state = self._read_payload()
            job = self._require_job(state, job_id)
            warnings = list(job.warnings)
            if warning and warning not in warnings:
                warnings.append(warning)

            event = ReportJobEvent(
                event_id=len(job.events),
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )

            updated_report = report or job.report
            updates = {
                "events": [*job.events, event],
                "warnings": warnings,
                "error": error,
                "report": updated_report,
                "artifacts": artifacts or job.artifacts,
                "activity": activity or job.activity,
                "workflow": workflow or job.workflow,
            }
            if status is not None:
                updates["status"] = status
            if progress is not None:
                updates["progress"] = progress

            updated = job.model_copy(update=updates)
            state["jobs"][job_id] = updated.model_dump(mode="json")
            if updated_report is not None:
                state["reports"][updated_report.report_id] = updated_report.model_dump(mode="json")
            self._write_payload(state)
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
            progress=100,
            error=message,
            report=failed_report,
        )

    def _read_payload(self) -> dict[str, dict]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                jobs = data.get("jobs")
                reports = data.get("reports")
                if isinstance(jobs, dict) and isinstance(reports, dict):
                    return {"jobs": jobs, "reports": reports}
        except Exception:
            pass
        return {"jobs": {}, "reports": {}}

    def _write_payload(self, payload: dict[str, dict]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _require_job(
        self,
        payload: dict[str, dict],
        job_id: str,
    ) -> ReportGenerationJobRecord:
        job_data = payload["jobs"].get(job_id)
        if not job_data:
            raise KeyError(f"Unknown job_id: {job_id}")
        return ReportGenerationJobRecord.model_validate(job_data)
