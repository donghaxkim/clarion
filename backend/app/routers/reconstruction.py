import asyncio

from fastapi import APIRouter, HTTPException, Request, status

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
from app.utils.storage import materialize_browser_uri

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
async def get_reconstruction_job(job_id: str, request: Request):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return _materialize_job_for_client(job, request=request)


def _materialize_job_for_client(
    job: ReconstructionJobStatusResponse,
    *,
    request: Request,
) -> ReconstructionJobStatusResponse:
    if job.result is None:
        return job

    try:
        result = job.result.model_copy(
            update={
                "video_url": materialize_browser_uri(
                    job.result.video_url or job.result.video_gcs_uri,
                    base_url=str(request.base_url),
                )
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to materialize a browser URL for reconstruction video "
                f"{job.result.video_gcs_uri!r}."
            ),
        ) from exc

    return job.model_copy(update={"result": result})
