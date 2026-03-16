from __future__ import annotations

import os
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schema import new_id
from app.services.case_service import case_workspace_service
from app.utils.storage import upload_bytes

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/clarion-uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


@router.post("/")
async def upload_files(files: list[UploadFile]):
    # TODO: store in GCS, return document IDs
    return {"uploaded": [f.filename for f in files]}


@router.post("/cases/{case_id}")
async def upload_case_files(
    case_id: str,
    files: list[UploadFile] = File(...),
):
    if case_workspace_service.get_case_record(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_workspace_service.mark_upload_started(case_id)
    parsed_results: list[dict[str, object]] = []
    pending_videos: list[dict[str, object]] = []

    try:
        for file in files:
            filename = file.filename or "unknown"
            file_type = _detect_file_type(filename)
            local_path, file_bytes = await _save_upload(file)
            content_type = file.content_type or "application/octet-stream"

            if file_type == "video":
                pending_id = new_id()
                media_url = _persist_raw_upload(
                    case_id=case_id,
                    object_id=pending_id,
                    filename=filename,
                    data=file_bytes,
                    content_type=content_type,
                )
                pending = {
                    "evidence_id": pending_id,
                    "filename": filename,
                    "media_url": media_url,
                    "file_type": "video",
                    "status": "pending_video_analysis",
                }
                case_workspace_service.add_pending_video(case_id, pending)
                pending_videos.append(pending)
                _cleanup_upload(local_path)
                continue

            try:
                evidence = _parse_evidence(local_path, filename, "")
                if evidence is None:
                    parsed_results.append(
                        {
                            "filename": filename,
                            "status": "parse_failed",
                            "error": "Could not parse file",
                        }
                    )
                    continue

                evidence.media.url = _persist_raw_upload(
                    case_id=case_id,
                    object_id=evidence.id,
                    filename=filename,
                    data=file_bytes,
                    content_type=content_type,
                )
                case_workspace_service.attach_evidence(case_id, evidence)
                parsed_results.append(
                    {
                        "evidence_id": evidence.id,
                        "filename": evidence.filename,
                        "evidence_type": getattr(
                            evidence.evidence_type,
                            "value",
                            evidence.evidence_type,
                        ),
                        "labels": list(evidence.labels),
                        "summary": evidence.summary,
                        "entity_count": len(evidence.entities),
                        "entities": [
                            {"type": entity.type, "name": entity.name}
                            for entity in evidence.entities
                        ],
                        "status": "parsed",
                    }
                )
            except Exception as exc:
                parsed_results.append(
                    {
                        "filename": filename,
                        "status": "parse_failed",
                        "error": str(exc),
                    }
                )
            finally:
                _cleanup_upload(local_path)
    finally:
        case_workspace_service.mark_upload_finished(case_id)

    record = case_workspace_service.require_case_record(case_id)
    return {
        "case_id": case_id,
        "parsed": parsed_results,
        "video_pending": pending_videos,
        "total_evidence": len(record.case.evidence),
        "total_entities": len(record.case.entities),
    }


async def _save_upload(file: UploadFile) -> tuple[str, bytes]:
    file_id = new_id()
    filename = file.filename or f"upload_{file_id}"
    suffix = Path(filename).suffix
    file_bytes = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=UPLOAD_DIR,
        prefix=f"{file_id}_",
        suffix=suffix,
    ) as tmp:
        tmp.write(file_bytes)
        local_path = tmp.name
    return local_path, file_bytes


def _persist_raw_upload(
    *,
    case_id: str,
    object_id: str,
    filename: str,
    data: bytes,
    content_type: str,
) -> str:
    safe_filename = Path(filename).name
    gcs_key = f"cases/{case_id}/uploads/{object_id}/{safe_filename}"
    return upload_bytes(data=data, gcs_key=gcs_key, content_type=content_type)


def _cleanup_upload(local_path: str) -> None:
    try:
        Path(local_path).unlink(missing_ok=True)
    except Exception:
        pass


def _detect_file_type(filename: str) -> str:
    from app.services.parser.labeler import detect_file_type

    return detect_file_type(filename)


def _parse_evidence(local_path: str, filename: str, media_url: str):
    from app.services.parser.labeler import parse_evidence

    return parse_evidence(local_path, filename, media_url)
