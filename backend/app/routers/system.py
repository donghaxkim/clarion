from __future__ import annotations

from fastapi import APIRouter

from app.services.case_service import case_workspace_service

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "cases_in_memory": case_workspace_service.count_cases(),
    }
