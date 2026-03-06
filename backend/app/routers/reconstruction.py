import asyncio

from fastapi import APIRouter, HTTPException, status

from app.config import RECONSTRUCTION_JOB_STORE_PATH, VEO_ALLOW_FAKE
from app.models import (
    ReconstructionCreateJobResponse,
    ReconstructionJobRequest,
    ReconstructionJobStatusResponse,
)
from app.services.video.reconstruction import (
    ReconstructionJobStore,
    ReconstructionOrchestrator,
    VeoClient,
)

router = APIRouter()

job_store = ReconstructionJobStore(path=RECONSTRUCTION_JOB_STORE_PATH)
orchestrator = ReconstructionOrchestrator(
    job_store=job_store,
    veo_client=VeoClient(allow_fake=VEO_ALLOW_FAKE),
)


@router.post("/jobs", response_model=ReconstructionCreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_reconstruction_job(payload: ReconstructionJobRequest):
    job = job_store.create_job()
    asyncio.create_task(orchestrator.run_job(job.job_id, payload))
    return ReconstructionCreateJobResponse(
        job_id=job.job_id,
        status=job.status,
        poll_url=f"/reconstruction/jobs/{job.job_id}",
    )


@router.get("/jobs/{job_id}", response_model=ReconstructionJobStatusResponse)
async def get_reconstruction_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job
