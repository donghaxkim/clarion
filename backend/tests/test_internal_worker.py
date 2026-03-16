import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    CaseEvidenceBundle,
    EvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
    ReportDocument,
)
from app.routers import internal
from app.services.case_service import CaseWorkspaceService, InMemoryCaseWorkspaceBackend
from app.services.generation.job_store import ReportJobStore
from app.services import intelligence_worker as intelligence_worker_service


def _report_request() -> GenerateReportRequest:
    return GenerateReportRequest(
        bundle=CaseEvidenceBundle(
            case_id="case-router",
            evidence_items=[
                EvidenceItem(
                    evidence_id="ev-1",
                    kind=EvidenceItemType.transcript,
                    summary="Witness statement",
                )
            ],
        ),
        user_id="user-1",
    )


def test_execute_report_job_runs_orchestrator_for_claimed_job(monkeypatch, tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-1")
    job = store.create_job(report=report)
    payload = _report_request()
    store.save_request(job.job_id, payload)
    calls: list[tuple[str, str]] = []

    class _FakeOrchestrator:
        def __init__(self, *, job_store):
            assert job_store is store

        async def run_job(self, job_id, request_payload):
            calls.append((job_id, request_payload.user_id))

    monkeypatch.setattr(intelligence_worker_service, "ReportGenerationOrchestrator", _FakeOrchestrator)

    status = asyncio.run(intelligence_worker_service.execute_report_job(job.job_id, store=store))

    assert status == "processed"
    assert calls == [(job.job_id, "user-1")]


def test_execute_report_job_skips_duplicate_claim(tmp_path):
    store = ReportJobStore(str(tmp_path / "jobs.json"))
    report = ReportDocument(report_id="report-2")
    job = store.create_job(report=report)
    store.claim_job(job.job_id)

    status = asyncio.run(intelligence_worker_service.execute_report_job(job.job_id, store=store))

    assert status == "skipped"


def test_execute_case_analysis_skips_stale_revision():
    workspace_service = CaseWorkspaceService(backend=InMemoryCaseWorkspaceBackend())
    record = workspace_service.create_case(title="Case")
    record.case.evidence.append(object())
    record.evidence_revision = 2
    workspace_service._backend.save_case_record(record)

    status = intelligence_worker_service.execute_case_analysis(
        record.case.id,
        evidence_revision=1,
        workspace_service=workspace_service,
    )

    assert status == "stale"


def test_execute_case_analysis_skips_already_pending():
    workspace_service = CaseWorkspaceService(backend=InMemoryCaseWorkspaceBackend())
    record = workspace_service.create_case(title="Case")
    record.case.evidence.append(object())
    record.evidence_revision = 2
    record.analysis_status = "queued"
    record.analysis_target_revision = 2
    workspace_service._backend.save_case_record(record)

    status = intelligence_worker_service.execute_case_analysis(
        record.case.id,
        evidence_revision=2,
        workspace_service=workspace_service,
    )

    assert status == "skipped"


def test_internal_router_executes_report_job(monkeypatch):
    client = TestClient(app)
    calls: list[str] = []

    async def _fake_execute_report_job(job_id: str, *, store=None):
        del store
        calls.append(job_id)
        return "processed"

    monkeypatch.setattr(intelligence_worker_service, "execute_report_job", _fake_execute_report_job)

    response = client.post("/internal/report-jobs/job-123")

    assert response.status_code == 200
    assert response.json() == {"status": "processed", "job_id": "job-123"}
    assert calls == ["job-123"]


def test_internal_router_executes_case_analysis(monkeypatch):
    client = TestClient(app)
    calls: list[tuple[str, int]] = []

    def _fake_execute_case_analysis(case_id: str, *, evidence_revision: int, workspace_service=None):
        del workspace_service
        calls.append((case_id, evidence_revision))
        return "processed"

    monkeypatch.setattr(intelligence_worker_service, "execute_case_analysis", _fake_execute_case_analysis)

    response = client.post("/internal/case-analysis/case-123", json={"evidence_revision": 4})

    assert response.status_code == 200
    assert response.json() == {
        "status": "processed",
        "case_id": "case-123",
        "evidence_revision": 4,
    }
    assert calls == [("case-123", 4)]
