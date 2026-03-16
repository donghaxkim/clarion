from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import ReportBlock, ReportBlockType
from app.services.case_service import case_workspace_service
from app.services.generation import ReportJobStore
from app.utils.gemini_client import ask_gemini_json

router = APIRouter()

job_store = ReportJobStore()


class EditSectionPayload(BaseModel):
    case_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    canonical_block_id: str | None = None
    edit_target: Literal["title", "content"] | None = None


@router.post("/section")
async def edit_section(payload: EditSectionPayload):
    try:
        record = case_workspace_service.require_case_record(payload.case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc

    report_id = record.latest_report_id
    if not report_id:
        raise HTTPException(status_code=404, detail="Case has no generated report yet")

    report = job_store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    canonical_block_id = payload.canonical_block_id or payload.section_id
    block = next((item for item in report.sections if item.id == canonical_block_id), None)
    if block is None:
        raise HTTPException(status_code=404, detail="Section not found")

    target = payload.edit_target or _default_edit_target(payload.section_id, block)
    updated_block = _rewrite_block(block, instruction=payload.instruction, target=target)
    updated_report = report.model_copy(
        update={
            "sections": [
                updated_block if item.id == block.id else item
                for item in report.sections
            ]
        }
    )
    job_store.save_report(report.report_id, updated_report)
    case_workspace_service.sync_report_status(payload.case_id, status="completed")

    return {
        "case_id": payload.case_id,
        "report_id": report.report_id,
        "section_id": payload.section_id,
        "canonical_block_id": block.id,
        "status": "updated",
        "updated_section": updated_block.model_dump(mode="json"),
        "report": updated_report.model_dump(mode="json"),
    }


def _default_edit_target(section_id: str, block: ReportBlock) -> Literal["title", "content"]:
    if section_id.endswith("--heading") or block.type != ReportBlockType.text:
        return "title" if block.title else "content"
    return "content"


def _rewrite_block(
    block: ReportBlock,
    *,
    instruction: str,
    target: Literal["title", "content"],
) -> ReportBlock:
    current_text = block.title if target == "title" else block.content
    rewritten = _rewrite_text(
        current_text=current_text or "",
        instruction=instruction,
        target=target,
        block=block,
    )
    rewritten = rewritten.strip() or (current_text or "")

    if target == "title":
        return block.model_copy(update={"title": rewritten})
    return block.model_copy(update={"content": rewritten})


def _rewrite_text(
    *,
    current_text: str,
    instruction: str,
    target: Literal["title", "content"],
    block: ReportBlock,
) -> str:
    if not current_text:
        current_text = block.title or block.content or ""

    prompt = f"""You are editing one section of a litigation report.

Target field: {target}
Block type: {getattr(block.type, "value", block.type)}
Current title: {block.title or ""}
Current content:
{block.content or ""}

Instruction:
{instruction}

Rewrite only the requested target field. Preserve the factual meaning, tone, and legal framing unless the instruction explicitly asks to change them.

Return JSON:
{{
  "text": "the rewritten field only"
}}
"""

    try:
        response = ask_gemini_json(prompt=prompt, temperature=0.2)
        rewritten = str(response.get("text", "")).strip()
        if rewritten:
            return rewritten
    except Exception:
        pass

    return _deterministic_edit(current_text=current_text, instruction=instruction)


def _deterministic_edit(*, current_text: str, instruction: str) -> str:
    lowered = instruction.lower()
    if "concise" in lowered or "shorter" in lowered:
        return current_text[: max(40, int(len(current_text) * 0.75))].rstrip()
    if "emphasis" in lowered or "emphasize" in lowered:
        return f"{current_text} {instruction}".strip()
    return current_text
