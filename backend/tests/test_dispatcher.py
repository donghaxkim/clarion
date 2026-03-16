import json

from app.services.cloud.dispatch import CloudRunJobDispatcher


class _RecordingClient:
    def __init__(self):
        self.requests: list[dict] = []

    def create_task(self, request):
        self.requests.append(request)
        return type("Task", (), {"name": request["task"]["name"]})()


def test_dispatch_report_job_builds_cloud_task_request():
    client = _RecordingClient()
    dispatcher = CloudRunJobDispatcher(
        client=client,
        project_id="clarion-project",
        location="us-central1",
        service_account_email="runner@clarion-project.iam.gserviceaccount.com",
        intelligence_worker_base_url="https://clarion-intelligence-worker.run.app",
        intelligence_worker_audience="https://clarion-intelligence-worker.run.app",
        report_queue="clarion-report-jobs",
        report_task_deadline_seconds=1800,
    )

    task_name = dispatcher.dispatch_report_job("job-123")

    assert task_name.endswith("/tasks/report-job-123")
    request = client.requests[0]
    assert request["parent"] == "projects/clarion-project/locations/us-central1/queues/clarion-report-jobs"
    task = request["task"]
    assert task["name"].endswith("/tasks/report-job-123")
    assert task["dispatch_deadline"] == "1800s"
    http_request = task["http_request"]
    assert http_request["url"] == "https://clarion-intelligence-worker.run.app/internal/report-jobs/job-123"
    assert http_request["oidc_token"]["service_account_email"] == (
        "runner@clarion-project.iam.gserviceaccount.com"
    )
    assert http_request["oidc_token"]["audience"] == "https://clarion-intelligence-worker.run.app"
    assert "body" not in http_request


def test_dispatch_reconstruction_job_treats_duplicate_task_as_success():
    class AlreadyExistsError(Exception):
        pass

    class _DuplicateClient:
        def create_task(self, request):
            raise AlreadyExistsError("Task already exists")

    dispatcher = CloudRunJobDispatcher(
        client=_DuplicateClient(),
        project_id="clarion-project",
        location="us-central1",
        service_account_email="runner@clarion-project.iam.gserviceaccount.com",
        reconstruction_queue="clarion-reconstruction-jobs",
        reconstruction_job_name="clarion-reconstruction-worker",
    )

    task_name = dispatcher.dispatch_reconstruction_job("job-456")

    assert task_name.endswith(
        "/queues/clarion-reconstruction-jobs/tasks/reconstruction-job-456"
    )


def test_dispatch_case_analysis_builds_cloud_task_request():
    client = _RecordingClient()
    dispatcher = CloudRunJobDispatcher(
        client=client,
        project_id="clarion-project",
        location="us-central1",
        service_account_email="runner@clarion-project.iam.gserviceaccount.com",
        intelligence_worker_base_url="https://clarion-intelligence-worker.run.app",
        intelligence_worker_audience="https://clarion-intelligence-worker.run.app",
        analysis_queue="clarion-analysis-jobs",
        analysis_task_deadline_seconds=900,
    )

    task_name = dispatcher.dispatch_case_analysis("case-123", 4)

    assert task_name.endswith("/tasks/analysis-case-123-4")
    request = client.requests[0]
    assert request["parent"] == "projects/clarion-project/locations/us-central1/queues/clarion-analysis-jobs"
    task = request["task"]
    assert task["name"].endswith("/tasks/analysis-case-123-4")
    assert task["dispatch_deadline"] == "900s"
    http_request = task["http_request"]
    assert http_request["url"] == (
        "https://clarion-intelligence-worker.run.app/internal/case-analysis/case-123"
    )
    assert http_request["oidc_token"]["service_account_email"] == (
        "runner@clarion-project.iam.gserviceaccount.com"
    )
    body = json.loads(http_request["body"].decode("utf-8"))
    assert body == {"evidence_revision": 4}
