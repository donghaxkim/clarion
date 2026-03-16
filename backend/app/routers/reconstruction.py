import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.models import (
    ReconstructionCreateJobResponse,
    ReconstructionJobRequest,
    ReconstructionJobStatusResponse,
)
from app.services.cloud import CloudRunJobDispatcher
from app.services.video.reconstruction import ReconstructionJobStore
from app.utils.storage import materialize_browser_uri

router = APIRouter()
logger = logging.getLogger(__name__)

job_store = ReconstructionJobStore()
dispatcher = CloudRunJobDispatcher()


@router.post("/jobs", response_model=ReconstructionCreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_reconstruction_job(payload: ReconstructionJobRequest):
    job = job_store.create_job()
    job_store.save_request(job.job_id, payload)
    dispatcher.dispatch_reconstruction_job(job.job_id)
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

    browser_url = _materialize_reconstruction_url(
        job.result.video_url or job.result.video_gcs_uri,
        request=request,
    )

    result = job.result.model_copy(
        update={
            "video_url": browser_url,
        }
    )

    return job.model_copy(update={"result": result})


def _materialize_reconstruction_url(uri: str | None, *, request: Request) -> str | None:
    try:
        return materialize_browser_uri(uri, base_url=str(request.base_url))
    except Exception as exc:
        logger.exception(
            "Failed to materialize reconstruction artifact URL for uri=%s",
            uri,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Artifact URL signing is unavailable for reconstruction video {uri!r}. "
                f"{exc}"
            ),
        ) from exc
