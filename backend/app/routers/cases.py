from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.models import ReportGenerationJobStatusResponse, ReportGenerationJobStatus, ReportStatus
from app.routers import generate as generate_router
from app.services.case_service import case_workspace_service

router = APIRouter()
logger = logging.getLogger(__name__)


class CaseCreateRequest(BaseModel):
    title: str | None = None
    case_type: str | None = None
    description: str | None = None


@router.post("")
async def create_case(payload: CaseCreateRequest):
    record = case_workspace_service.create_case(
        title=payload.title,
        case_type=payload.case_type,
        description=payload.description,
    )
    return {
        "case_id": record.case.id,
        "status": record.case.status,
        "created_at": record.case.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.get("/{case_id}")
async def get_case(case_id: str):
    try:
        return case_workspace_service.serialize_case(
            case_id,
            report_store=generate_router.job_store,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.post("/{case_id}/analyze")
async def analyze_case(case_id: str):
    try:
        record = case_workspace_service.analyze_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    index = record.citation_index
    case_payload = case_workspace_service.serialize_case(
        case_id,
        report_store=generate_router.job_store,
    )
    serialized_contradictions = case_payload["contradictions"]
    serialized_missing_info = case_payload["missing_info"]

    return {
        "case_id": record.case.id,
        "case_type_detected": index.case_type if index is not None else record.case.case_type,
        "dimensions_discovered": list(index.dimensions) if index is not None else [],
        "total_facts_indexed": len(index.facts) if index is not None else 0,
        "total_entities": len(record.case.entities),
        "entities": [
            {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "aliases": list(entity.aliases),
                "mention_count": len(entity.mentions),
            }
            for entity in record.case.entities
        ],
        "contradictions": {
            "summary": {
                "total": len(serialized_contradictions),
                "high": sum(1 for item in serialized_contradictions if item["severity"] == "high"),
                "medium": sum(1 for item in serialized_contradictions if item["severity"] == "medium"),
                "low": sum(1 for item in serialized_contradictions if item["severity"] == "low"),
            },
            "items": serialized_contradictions,
        },
        "missing_info": {
            "total": len(serialized_missing_info),
            "critical": sum(
                1
                for item in serialized_missing_info
                if item["severity"] == "high"
            ),
            "items": serialized_missing_info,
        },
    }


@router.get("/{case_id}/entities/{entity_name}")
async def get_entity_details(case_id: str, entity_name: str):
    try:
        return case_workspace_service.get_entity_payload(case_id, entity_name)
    except KeyError as exc:
        detail = "Case not found" if "case_id" in str(exc) else "Entity not found"
        raise HTTPException(status_code=404, detail=detail) from exc


@router.post("/{case_id}/report-jobs", status_code=202)
async def create_case_report_job(case_id: str):
    try:
        payload = case_workspace_service.build_generate_request(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accepted = generate_router.enqueue_report_job(payload)
    case_workspace_service.record_latest_report_refs(
        case_id,
        report_id=accepted.report_id,
        job_id=accepted.job_id,
    )
    try:
        _record, revision, should_dispatch = case_workspace_service.queue_analysis_for_current_revision(
            case_id
        )
    except ValueError:
        should_dispatch = False
        revision = 0

    if should_dispatch:
        try:
            generate_router.dispatcher.dispatch_case_analysis(case_id, revision)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Failed to dispatch case analysis for case_id=%s revision=%s",
                case_id,
                revision,
            )
            case_workspace_service.mark_analysis_dispatch_failed(
                case_id,
                expected_revision=revision,
                message=str(exc),
            )
    body = accepted.model_dump(mode="json")
    body["case_id"] = case_id
    return body


@router.get("/{case_id}/report")
async def get_case_report(case_id: str, request: Request):
    try:
        record = case_workspace_service.require_case_record(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc

    if record.latest_report_job_id:
        job = generate_router.get_materialized_job_status(
            record.latest_report_job_id,
            request=request,
        )
        case_workspace_service.sync_report_status(case_id, status=job.status.value)
        payload = job.model_dump(mode="json")
        payload["case_id"] = case_id
        return payload

    if record.latest_report_id:
        report = generate_router.get_materialized_report(
            record.latest_report_id,
            request=request,
        )
        synthetic = ReportGenerationJobStatusResponse(
            job_id="",
            report_id=record.latest_report_id,
            status=ReportGenerationJobStatus.completed,
            progress=100,
            warnings=list(report.warnings),
            report=report.model_copy(update={"status": ReportStatus.completed}),
            artifacts=None,
            activity=None,
            workflow=None,
        )
        payload = synthetic.model_dump(mode="json")
        payload["case_id"] = case_id
        return payload

    raise HTTPException(status_code=404, detail="Case has no generated report yet")
