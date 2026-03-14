from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.case_service import case_workspace_service
from app.services.intelligence.contradictions import summarize_contradictions

router = APIRouter()


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
        return case_workspace_service.serialize_case(case_id)
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
    contradictions = record.case.contradictions

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
                "mention_count": len(entity.mentions),
            }
            for entity in record.case.entities
        ],
        "contradictions": {
            "summary": summarize_contradictions(contradictions),
            "items": [
                {
                    "id": contradiction.id,
                    "severity": getattr(contradiction.severity, "value", contradiction.severity),
                    "description": contradiction.description,
                    "fact_a": contradiction.fact_a,
                    "fact_b": contradiction.fact_b,
                }
                for contradiction in contradictions
            ],
        },
    }


@router.get("/{case_id}/entities/{entity_name}")
async def get_entity_details(case_id: str, entity_name: str):
    try:
        return case_workspace_service.get_entity_payload(case_id, entity_name)
    except KeyError as exc:
        detail = "Case not found" if "case_id" in str(exc) else "Entity not found"
        raise HTTPException(status_code=404, detail=detail) from exc
