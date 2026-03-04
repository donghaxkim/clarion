# POST /generate + SSE /stream
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models import ReportSection

router = APIRouter()


@router.post("/")
async def generate_report():
    # TODO: full report generation
    return {"sections": []}


@router.get("/stream")
async def stream_report():
    # TODO: SSE stream sections as they arrive
    async def event_stream():
        yield "data: {}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
