from __future__ import annotations

import json
from typing import Any

from app.config import (
    ANALYSIS_TASK_QUEUE,
    ANALYSIS_TASK_DEADLINE_SECONDS,
    CLOUD_RUN_JOBS_API_BASE_URL,
    CLOUD_RUN_REGION,
    CLOUD_TASKS_LOCATION,
    CLOUD_TASKS_PROJECT_ID,
    CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL,
    INTELLIGENCE_WORKER_AUDIENCE,
    INTELLIGENCE_WORKER_BASE_URL,
    GCP_PROJECT_ID,
    RECONSTRUCTION_TASK_QUEUE,
    RECONSTRUCTION_WORKER_JOB_NAME,
    REPORT_TASK_QUEUE,
    REPORT_TASK_DEADLINE_SECONDS,
)


class CloudRunJobDispatcher:
    def __init__(
        self,
        *,
        client: Any | None = None,
        project_id: str | None = None,
        location: str | None = None,
        service_account_email: str | None = None,
        api_base_url: str | None = None,
        intelligence_worker_base_url: str | None = None,
        intelligence_worker_audience: str | None = None,
        report_queue: str | None = None,
        analysis_queue: str | None = None,
        reconstruction_queue: str | None = None,
        report_task_deadline_seconds: int | None = None,
        analysis_task_deadline_seconds: int | None = None,
        reconstruction_job_name: str | None = None,
    ):
        self._client = client
        self.project_id = (project_id or CLOUD_TASKS_PROJECT_ID or GCP_PROJECT_ID).strip()
        self.location = (location or CLOUD_TASKS_LOCATION or CLOUD_RUN_REGION).strip()
        self.service_account_email = (
            service_account_email or CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL
        ).strip()
        self.api_base_url = (api_base_url or CLOUD_RUN_JOBS_API_BASE_URL).rstrip("/")
        self.intelligence_worker_base_url = (
            intelligence_worker_base_url or INTELLIGENCE_WORKER_BASE_URL
        ).rstrip("/")
        self.intelligence_worker_audience = (
            intelligence_worker_audience or INTELLIGENCE_WORKER_AUDIENCE
        ).strip()
        self.report_queue = (report_queue or REPORT_TASK_QUEUE).strip()
        self.analysis_queue = (analysis_queue or ANALYSIS_TASK_QUEUE).strip()
        self.reconstruction_queue = (reconstruction_queue or RECONSTRUCTION_TASK_QUEUE).strip()
        self.report_task_deadline_seconds = (
            REPORT_TASK_DEADLINE_SECONDS
            if report_task_deadline_seconds is None
            else report_task_deadline_seconds
        )
        self.analysis_task_deadline_seconds = (
            ANALYSIS_TASK_DEADLINE_SECONDS
            if analysis_task_deadline_seconds is None
            else analysis_task_deadline_seconds
        )
        self.reconstruction_job_name = (
            reconstruction_job_name or RECONSTRUCTION_WORKER_JOB_NAME
        ).strip()

    def dispatch_report_job(self, job_id: str) -> str:
        return self._enqueue_service_task(
            task_name=f"report-{job_id}",
            queue_name=self.report_queue,
            url=self._intelligence_worker_url(f"/internal/report-jobs/{job_id}"),
            deadline_seconds=self.report_task_deadline_seconds,
        )

    def dispatch_case_analysis(self, case_id: str, evidence_revision: int) -> str:
        return self._enqueue_service_task(
            task_name=f"analysis-{case_id}-{evidence_revision}",
            queue_name=self.analysis_queue,
            url=self._intelligence_worker_url(f"/internal/case-analysis/{case_id}"),
            deadline_seconds=self.analysis_task_deadline_seconds,
            body={"evidence_revision": evidence_revision},
        )

    def dispatch_reconstruction_job(self, job_id: str) -> str:
        return self._enqueue_job(
            task_name=f"reconstruction-{job_id}",
            queue_name=self.reconstruction_queue,
            worker_job_name=self.reconstruction_job_name,
            env_vars={"CLARION_JOB_ID": job_id},
        )

    def _enqueue_service_task(
        self,
        *,
        task_name: str,
        queue_name: str,
        url: str,
        deadline_seconds: int,
        body: dict[str, object] | None = None,
    ) -> str:
        client = self._get_client()
        parent = self._queue_path(queue_name)
        http_request: dict[str, object] = {
            "http_method": "POST",
            "url": url,
            "oidc_token": {
                "service_account_email": self._require_service_account_email(),
                "audience": self._require_intelligence_worker_audience(),
            },
        }
        if body is not None:
            http_request["headers"] = {"Content-Type": "application/json"}
            http_request["body"] = json.dumps(body).encode("utf-8")

        task = {
            "name": f"{parent}/tasks/{task_name}",
            "http_request": http_request,
            "dispatch_deadline": f"{max(1, min(deadline_seconds, 1800))}s",
        }

        try:
            created = client.create_task(request={"parent": parent, "task": task})
        except Exception as exc:
            if _is_already_exists_error(exc):
                return task["name"]
            raise
        return getattr(created, "name", task["name"])

    def _enqueue_job(
        self,
        *,
        task_name: str,
        queue_name: str,
        worker_job_name: str,
        env_vars: dict[str, str],
    ) -> str:
        client = self._get_client()
        parent = self._queue_path(queue_name)
        run_job_url = self._run_job_url(worker_job_name)
        task = {
            "name": f"{parent}/tasks/{task_name}",
            "http_request": {
                "http_method": "POST",
                "url": run_job_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(self._run_job_body(env_vars)).encode("utf-8"),
                "oauth_token": {
                    "service_account_email": self._require_service_account_email(),
                    "scope": "https://www.googleapis.com/auth/cloud-platform",
                },
            },
        }

        try:
            created = client.create_task(request={"parent": parent, "task": task})
        except Exception as exc:
            if _is_already_exists_error(exc):
                return task["name"]
            raise
        return getattr(created, "name", task["name"])

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import tasks_v2  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "google-cloud-tasks is required for Cloud Tasks dispatch. "
                "Install `google-cloud-tasks`."
            ) from exc

        self._client = tasks_v2.CloudTasksClient()
        return self._client

    def _queue_path(self, queue_name: str) -> str:
        if not self.project_id or not self.location or not queue_name:
            raise RuntimeError(
                "CLOUD_TASKS_PROJECT_ID/GCP_PROJECT_ID, CLOUD_TASKS_LOCATION, and queue names "
                "must be configured for task dispatch."
            )
        return f"projects/{self.project_id}/locations/{self.location}/queues/{queue_name}"

    def _run_job_url(self, worker_job_name: str) -> str:
        if not self.project_id or not self.location or not worker_job_name:
            raise RuntimeError(
                "GCP_PROJECT_ID/CLOUD_TASKS_PROJECT_ID, CLOUD_RUN_REGION, and worker job names "
                "must be configured for Cloud Run Job dispatch."
            )
        return (
            f"{self.api_base_url}/v2/projects/{self.project_id}/locations/"
            f"{self.location}/jobs/{worker_job_name}:run"
        )

    def _intelligence_worker_url(self, path: str) -> str:
        if not self.intelligence_worker_base_url:
            raise RuntimeError(
                "INTELLIGENCE_WORKER_BASE_URL must be configured for report and analysis dispatch"
            )
        return f"{self.intelligence_worker_base_url}{path}"

    def _require_service_account_email(self) -> str:
        if not self.service_account_email:
            raise RuntimeError(
                "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL must be configured for authenticated task dispatch"
            )
        return self.service_account_email

    def _require_intelligence_worker_audience(self) -> str:
        if not self.intelligence_worker_audience:
            raise RuntimeError(
                "INTELLIGENCE_WORKER_AUDIENCE or INTELLIGENCE_WORKER_BASE_URL must be configured "
                "for authenticated worker-service dispatch"
            )
        return self.intelligence_worker_audience

    @staticmethod
    def _run_job_body(env_vars: dict[str, str]) -> dict[str, object]:
        return {
            "overrides": {
                "containerOverrides": [
                    {
                        "env": [
                            {"name": name, "value": value}
                            for name, value in env_vars.items()
                        ]
                    }
                ]
            }
        }


def _is_already_exists_error(exc: BaseException) -> bool:
    class_name = type(exc).__name__.lower()
    if "alreadyexists" in class_name:
        return True
    return "already exists" in str(exc).lower()
