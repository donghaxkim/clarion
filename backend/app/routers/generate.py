import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse

from app.config import GCS_ALLOW_LOCAL_FALLBACK, LOCAL_ARTIFACTS_DIR, REPORT_JOB_STORE_PATH
from app.models import (
    Citation,
    GenerateReportJobAcceptedResponse,
    GenerateReportRequest,
    MediaAsset,
    ReportArtifactRefs,
    ReportBlock,
    ReportDocument,
    ReportGenerationJobStatus,
    ReportGenerationJobStatusResponse,
    ReportStatus,
)
from app.services.generation import ReportGenerationOrchestrator, ReportJobStore
from app.utils.storage import materialize_browser_uri

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
async def get_report_job(job_id: str, request: Request):
    job = job_store.get_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return _materialize_job_for_client(job, request=request)


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
async def get_report(report_id: str, request: Request):
    report = job_store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown report_id: {report_id}")
    return _materialize_report_for_client(report, request=request)


@router.get("/artifacts/{artifact_path:path}")
async def get_local_artifact(artifact_path: str):
    if not GCS_ALLOW_LOCAL_FALLBACK:
        raise HTTPException(status_code=404, detail="Local artifact fallback is disabled.")

    resolved_path = _resolve_local_artifact_path(artifact_path)
    if resolved_path is None or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown artifact path: {artifact_path}")

    return FileResponse(resolved_path)


def _encode_sse(event_type: str, payload: dict, event_id: int) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(payload)}\n\n"
    )


def _materialize_job_for_client(
    job: ReportGenerationJobStatusResponse,
    *,
    request: Request,
) -> ReportGenerationJobStatusResponse:
    report = (
        _materialize_report_for_client(job.report, request=request)
        if job.report is not None
        else None
    )
    artifacts = (
        _materialize_artifacts_for_client(job.artifacts, request=request)
        if job.artifacts is not None
        else None
    )
    return job.model_copy(update={"report": report, "artifacts": artifacts})


def _materialize_report_for_client(
    report: ReportDocument,
    *,
    request: Request,
) -> ReportDocument:
    sections = [
        _materialize_block_for_client(block, request=request)
        for block in report.sections
    ]
    return report.model_copy(update={"sections": sections})


def _materialize_block_for_client(
    block: ReportBlock,
    *,
    request: Request,
) -> ReportBlock:
    citations = [
        _materialize_citation_for_client(citation, request=request)
        for citation in block.citations
    ]
    media = [
        _materialize_media_asset_for_client(asset, request=request)
        for asset in block.media
    ]
    return block.model_copy(update={"citations": citations, "media": media})


def _materialize_citation_for_client(
    citation: Citation,
    *,
    request: Request,
) -> Citation:
    return citation.model_copy(
        update={
            "uri": _materialize_optional_uri(citation.uri, request=request),
        }
    )


def _materialize_media_asset_for_client(
    asset: MediaAsset,
    *,
    request: Request,
) -> MediaAsset:
    return asset.model_copy(
        update={
            "uri": _materialize_required_uri(asset.uri, request=request),
            "manifest_uri": _materialize_optional_uri(asset.manifest_uri, request=request),
        }
    )


def _materialize_artifacts_for_client(
    artifacts: ReportArtifactRefs,
    *,
    request: Request,
) -> ReportArtifactRefs:
    browser_report_uri = artifacts.report_url or artifacts.report_gcs_uri
    return artifacts.model_copy(
        update={
            "report_url": _materialize_optional_uri(browser_report_uri, request=request),
        }
    )


def _materialize_required_uri(uri: str | None, *, request: Request) -> str | None:
    try:
        return materialize_browser_uri(uri, base_url=str(request.base_url))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to materialize a browser URL for artifact {uri!r}.",
        ) from exc


def _materialize_optional_uri(uri: str | None, *, request: Request) -> str | None:
    if uri is None:
        return None

    try:
        return materialize_browser_uri(uri, base_url=str(request.base_url))
    except Exception:
        return None


def _resolve_local_artifact_path(artifact_path: str) -> Path | None:
    base_dir = Path(LOCAL_ARTIFACTS_DIR).resolve()
    candidate = (base_dir / artifact_path).resolve()
    if candidate == base_dir or base_dir in candidate.parents:
        return candidate
    return None
