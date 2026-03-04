# GET /export
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/")
async def export_report(format: str = "pdf"):
    # TODO: convert report to PDF/DOCX and return file
    return {"message": f"export as {format}"}
