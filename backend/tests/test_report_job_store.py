from app.models import ReportDocument, ReportGenerationJobStatus, ReportStatus
from app.services.generation.job_store import ReportJobStore


def test_job_store_clamps_non_terminal_progress_updates(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    job = store.create_job(
        report=ReportDocument(report_id="report-1", status=ReportStatus.running)
    )

    store.publish(
        job.job_id,
        event_type="job.started",
        payload={"report_id": "report-1"},
        status=ReportGenerationJobStatus.planning,
        progress=52,
        report=job.report,
    )
    store.publish(
        job.job_id,
        event_type="job.activity",
        payload={"activity": None},
        status=ReportGenerationJobStatus.planning,
        progress=40,
        report=job.report,
    )

    updated = store.get_job(job.job_id)
    assert updated is not None
    assert updated.progress == 52


def test_job_store_preserves_last_progress_when_job_fails(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    job = store.create_job(
        report=ReportDocument(report_id="report-2", status=ReportStatus.running)
    )

    store.publish(
        job.job_id,
        event_type="timeline.ready",
        payload={"sections": 2, "warnings": []},
        status=ReportGenerationJobStatus.composing,
        progress=78,
        report=job.report,
    )
    store.mark_failed(job.job_id, "pipeline blew up")

    failed = store.get_job(job.job_id)
    assert failed is not None
    assert failed.status == ReportGenerationJobStatus.failed
    assert failed.progress == 78
