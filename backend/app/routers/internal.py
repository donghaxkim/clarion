from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import intelligence_worker as intelligence_worker_service

router = APIRouter()


class CaseAnalysisTaskRequest(BaseModel):
    evidence_revision: int = Field(ge=1)


@router.post("/report-jobs/{job_id}")
async def execute_report_job(job_id: str):
    status = await intelligence_worker_service.execute_report_job(job_id)
    return {"status": status, "job_id": job_id}


@router.post("/case-analysis/{case_id}")
async def execute_case_analysis(case_id: str, payload: CaseAnalysisTaskRequest):
    status = intelligence_worker_service.execute_case_analysis(
        case_id,
        evidence_revision=payload.evidence_revision,
    )
    return {
        "status": status,
        "case_id": case_id,
        "evidence_revision": payload.evidence_revision,
    }
