import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import REPORT_JOB_STORE_PATH
from app.models import (
    GenerateReportJobAcceptedResponse,
    GenerateReportRequest,
    ReportDocument,
    ReportGenerationJobStatus,
    ReportGenerationJobStatusResponse,
    ReportStatus,
)
from app.services.generation import ReportGenerationOrchestrator, ReportJobStore

router = APIRouter()

job_store = ReportJobStore(path=REPORT_JOB_STORE_PATH)
orchestrator = ReportGenerationOrchestrator(job_store=job_store)


@router.post("/jobs", response_model=GenerateReportJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_report_job(payload: GenerateReportRequest):
    report_id = str(uuid.uuid4())
    report = ReportDocument(report_id=report_id, status=ReportStatus.running)
    job = job_store.create_job(report=report)
    asyncio.create_task(orchestrator.run_job(job.job_id, payload))
    return GenerateReportJobAcceptedResponse(
        job_id=job.job_id,
        report_id=report_id,
        status_url=f"/generate/jobs/{job.job_id}",
        stream_url=f"/generate/jobs/{job.job_id}/stream",
        report_url=f"/generate/reports/{report_id}",
    )


@router.get("/jobs/{job_id}", response_model=ReportGenerationJobStatusResponse)
async def get_report_job(job_id: str):
    job = job_store.get_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job


@router.get("/jobs/{job_id}/stream")
async def stream_report_job(job_id: str):
    if job_store.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    async def event_stream():
        last_event_id = -1
        while True:
            events = job_store.get_events_since(job_id, last_event_id)
            if events:
                for event in events:
                    last_event_id = event.event_id
                    yield _encode_sse(event.event_type, event.payload, event.event_id)
            job = job_store.get_job(job_id)
            if job is None:
                break
            if job.status in {ReportGenerationJobStatus.completed, ReportGenerationJobStatus.failed}:
                latest_event_id = job.events[-1].event_id if job.events else -1
                if last_event_id >= latest_event_id:
                    break
            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/reports/{report_id}", response_model=ReportDocument)
async def get_report(report_id: str):
    report = job_store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown report_id: {report_id}")
    return report


def _encode_sse(event_type: str, payload: dict, event_id: int) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(payload)}\n\n"
    )
