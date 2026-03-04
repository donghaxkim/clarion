# POST /upload endpoint
from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/")
async def upload_files(files: list[UploadFile]):
    # TODO: store in GCS, return document IDs
    return {"uploaded": [f.filename for f in files]}
