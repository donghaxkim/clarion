from fastapi.testclient import TestClient

from app.main import app
from app.models import ReportBlock, ReportProvenance, ReportStatus, ReportDocument
from app.routers import edit
from app.services.case_service import case_workspace_service
from app.services.generation.job_store import ReportJobStore


def setup_function():
    case_workspace_service.clear()


def teardown_function():
    case_workspace_service.clear()


def test_edit_section_rewrites_latest_case_report(monkeypatch, tmp_path):
    record = case_workspace_service.create_case(
        title="Smith v. Johnson",
        description="Rear-end collision at an intersection.",
    )

    store = ReportJobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(edit, "job_store", store)
    monkeypatch.setattr(edit, "ask_gemini_json", lambda **kwargs: {"text": "Updated section text."})

    report = ReportDocument(
        report_id="report-edit-1",
        status=ReportStatus.completed,
        sections=[
            ReportBlock(
                id="impact-summary",
                type="text",
                title="Impact Summary",
                content="Original section text.",
                sort_key="0001",
                provenance=ReportProvenance.evidence,
            )
        ],
    )
    job = store.create_job(report=report)
    store.save_report(report.report_id, report)
    case_workspace_service.record_latest_report_refs(
        record.case.id,
        report_id=report.report_id,
        job_id=job.job_id,
    )

    client = TestClient(app)
    response = client.post(
        "/edit/section",
        json={
            "case_id": record.case.id,
            "section_id": "impact-summary",
            "instruction": "Make this more concise.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "updated"
    assert payload["report_id"] == report.report_id
    assert payload["updated_section"]["content"] == "Updated section text."

    saved_report = store.get_report(report.report_id)
    assert saved_report is not None
    assert saved_report.sections[0].content == "Updated section text."
