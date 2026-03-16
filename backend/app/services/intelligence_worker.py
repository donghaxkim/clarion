from __future__ import annotations

from app.services.case_service import (
    ANALYSIS_PENDING_STATUSES,
    ANALYSIS_STATUS_COMPLETED,
    CaseWorkspaceService,
    case_workspace_service,
)
from app.services.generation import ReportGenerationOrchestrator, ReportJobStore

report_job_store = ReportJobStore()


async def execute_report_job(
    job_id: str,
    *,
    store: ReportJobStore | None = None,
) -> str:
    store = store or report_job_store
    if not store.claim_job(job_id):
        return "skipped"

    payload = store.load_request(job_id)
    orchestrator = ReportGenerationOrchestrator(job_store=store)
    await orchestrator.run_job(job_id, payload)
    return "processed"


def execute_case_analysis(
    case_id: str,
    *,
    evidence_revision: int,
    workspace_service: CaseWorkspaceService | None = None,
) -> str:
    workspace_service = workspace_service or case_workspace_service
    record = workspace_service.get_case_record(case_id)
    if record is None:
        return "missing"
    if record.evidence_revision != evidence_revision:
        return "stale"
    if (
        record.analysis_revision == evidence_revision
        and record.analysis_status == ANALYSIS_STATUS_COMPLETED
    ):
        return "skipped"
    if (
        record.analysis_status in ANALYSIS_PENDING_STATUSES
        and record.analysis_target_revision == evidence_revision
    ):
        return "skipped"

    workspace_service.run_analysis(case_id, expected_revision=evidence_revision)
    return "processed"
