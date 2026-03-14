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
        api_base_url="https://run.googleapis.com",
        report_queue="clarion-report-jobs",
        report_job_name="clarion-report-worker",
    )

    task_name = dispatcher.dispatch_report_job("job-123")

    assert task_name.endswith("/tasks/report-job-123")
    request = client.requests[0]
    assert request["parent"] == "projects/clarion-project/locations/us-central1/queues/clarion-report-jobs"
    task = request["task"]
    assert task["name"].endswith("/tasks/report-job-123")
    http_request = task["http_request"]
    assert http_request["url"] == (
        "https://run.googleapis.com/v2/projects/clarion-project/locations/us-central1/"
        "jobs/clarion-report-worker:run"
    )
    assert http_request["oauth_token"]["service_account_email"] == (
        "runner@clarion-project.iam.gserviceaccount.com"
    )

    body = json.loads(http_request["body"].decode("utf-8"))
    overrides = body["overrides"]["containerOverrides"][0]
    assert overrides["env"] == [{"name": "CLARION_JOB_ID", "value": "job-123"}]


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
