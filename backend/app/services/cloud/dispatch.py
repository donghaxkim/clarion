from __future__ import annotations

import json
from typing import Any

from app.config import (
    CLOUD_RUN_JOBS_API_BASE_URL,
    CLOUD_RUN_REGION,
    CLOUD_TASKS_LOCATION,
    CLOUD_TASKS_PROJECT_ID,
    CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL,
    GCP_PROJECT_ID,
    RECONSTRUCTION_TASK_QUEUE,
    RECONSTRUCTION_WORKER_JOB_NAME,
    REPORT_TASK_QUEUE,
    REPORT_WORKER_JOB_NAME,
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
        report_queue: str | None = None,
        reconstruction_queue: str | None = None,
        report_job_name: str | None = None,
        reconstruction_job_name: str | None = None,
    ):
        self._client = client
        self.project_id = (project_id or CLOUD_TASKS_PROJECT_ID or GCP_PROJECT_ID).strip()
        self.location = (location or CLOUD_TASKS_LOCATION or CLOUD_RUN_REGION).strip()
        self.service_account_email = (
            service_account_email or CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL
        ).strip()
        self.api_base_url = (api_base_url or CLOUD_RUN_JOBS_API_BASE_URL).rstrip("/")
        self.report_queue = (report_queue or REPORT_TASK_QUEUE).strip()
        self.reconstruction_queue = (reconstruction_queue or RECONSTRUCTION_TASK_QUEUE).strip()
        self.report_job_name = (report_job_name or REPORT_WORKER_JOB_NAME).strip()
        self.reconstruction_job_name = (
            reconstruction_job_name or RECONSTRUCTION_WORKER_JOB_NAME
        ).strip()

    def dispatch_report_job(self, job_id: str) -> str:
        return self._enqueue_job(
            task_name=f"report-{job_id}",
            queue_name=self.report_queue,
            worker_job_name=self.report_job_name,
            job_id=job_id,
        )

    def dispatch_reconstruction_job(self, job_id: str) -> str:
        return self._enqueue_job(
            task_name=f"reconstruction-{job_id}",
            queue_name=self.reconstruction_queue,
            worker_job_name=self.reconstruction_job_name,
            job_id=job_id,
        )

    def _enqueue_job(
        self,
        *,
        task_name: str,
        queue_name: str,
        worker_job_name: str,
        job_id: str,
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
                "body": json.dumps(self._run_job_body(job_id)).encode("utf-8"),
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

    def _require_service_account_email(self) -> str:
        if not self.service_account_email:
            raise RuntimeError(
                "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL must be configured for authenticated task dispatch"
            )
        return self.service_account_email

    @staticmethod
    def _run_job_body(job_id: str) -> dict[str, object]:
        return {
            "overrides": {
                "containerOverrides": [
                    {
                        "env": [
                            {
                                "name": "CLARION_JOB_ID",
                                "value": job_id,
                            }
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
