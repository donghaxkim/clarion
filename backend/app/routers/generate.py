import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.agents.reporting.progress import build_queued_activity, build_workflow_state
from app.config import (
    REPORT_ENABLE_PUBLIC_CONTEXT,
)
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
from app.services.cloud import CloudRunJobDispatcher
from app.services.generation import ReportJobStore
from app.services.generation.report_citations import normalize_report_document
from app.utils.storage import materialize_browser_uri

router = APIRouter()
logger = logging.getLogger(__name__)

job_store = ReportJobStore()
dispatcher = CloudRunJobDispatcher()


@router.post("/jobs", response_model=GenerateReportJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_report_job(payload: GenerateReportRequest):
    return enqueue_report_job(payload)


def enqueue_report_job(
    payload: GenerateReportRequest,
    *,
    store: ReportJobStore | None = None,
    job_dispatcher: CloudRunJobDispatcher | None = None,
) -> GenerateReportJobAcceptedResponse:
    store = store or job_store
    job_dispatcher = job_dispatcher or dispatcher
    report_id = str(uuid.uuid4())
    report = ReportDocument(report_id=report_id, status=ReportStatus.running)
    workflow = build_workflow_state(
        enable_public_context=(
            payload.enable_public_context
            if payload.enable_public_context is not None
            else REPORT_ENABLE_PUBLIC_CONTEXT
        )
    )
    job = store.create_job(
        report=report,
        activity=build_queued_activity(),
        workflow=workflow,
    )
    store.save_request(job.job_id, payload)
    job_dispatcher.dispatch_report_job(job.job_id)
    return GenerateReportJobAcceptedResponse(
        job_id=job.job_id,
        report_id=report_id,
        status_url=f"/generate/jobs/{job.job_id}",
        stream_url=f"/generate/jobs/{job.job_id}/stream",
        report_url=f"/generate/reports/{report_id}",
    )


@router.get("/jobs/{job_id}", response_model=ReportGenerationJobStatusResponse)
async def get_report_job(job_id: str, request: Request):
    return get_materialized_job_status(job_id, request=request)


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
    return get_materialized_report(report_id, request=request)


def get_materialized_job_status(
    job_id: str,
    *,
    request: Request,
    store: ReportJobStore | None = None,
) -> ReportGenerationJobStatusResponse:
    store = store or job_store
    job = store.get_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    if job.report is not None:
        request_payload = store.get_request_for_report(job.report_id)
        report = _normalize_report_for_delivery(
            job.report,
            store=store,
            request_payload=request_payload,
        )
        job = job.model_copy(update={"report": report})
    return _materialize_job_for_client(job, request=request)


def get_materialized_report(
    report_id: str,
    *,
    request: Request,
    store: ReportJobStore | None = None,
) -> ReportDocument:
    store = store or job_store
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown report_id: {report_id}")
    request_payload = store.get_request_for_report(report_id)
    report = _normalize_report_for_delivery(
        report,
        store=store,
        request_payload=request_payload,
    )
    return _materialize_report_for_client(report, request=request)


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
        return _raise_artifact_materialization_error(uri, exc)


def _materialize_optional_uri(uri: str | None, *, request: Request) -> str | None:
    if uri is None:
        return None

    try:
        return materialize_browser_uri(uri, base_url=str(request.base_url))
    except Exception as exc:
        return _raise_artifact_materialization_error(uri, exc)


def _raise_artifact_materialization_error(uri: str | None, exc: Exception) -> None:
    logger.exception(
        "Failed to materialize report artifact URL for uri=%s",
        uri,
    )
    raise HTTPException(
        status_code=500,
        detail=f"Artifact URL signing is unavailable for {uri!r}. {exc}",
    ) from exc


def _normalize_report_for_delivery(
    report: ReportDocument,
    *,
    store: ReportJobStore,
    request_payload: GenerateReportRequest | None,
) -> ReportDocument:
    normalized_report, changed = normalize_report_document(
        report,
        bundle=(request_payload.bundle if request_payload is not None else None),
    )
    if changed:
        try:
            store.save_report(report.report_id, normalized_report)
        except Exception:
            logger.exception(
                "Failed to persist canonical citation upgrade for report_id=%s",
                report.report_id,
            )
    return normalized_report
