from __future__ import annotations

from datetime import UTC, datetime

from app.agents.reporting.types import ComposedBlockDraft, MediaRequest, PipelineResult
from app.models import (
    MediaAsset,
    ReportBlock,
    ReportBlockState,
    ReportDocument,
    ReportProvenance,
    ReportStatus,
)


def create_initial_report(report_id: str, draft: PipelineResult) -> ReportDocument:
    blocks = [_draft_to_block(block) for block in draft.blocks]
    blocks.extend(_media_request_to_block(request) for request in draft.image_requests)
    blocks.extend(_media_request_to_block(request) for request in draft.reconstruction_requests)
    blocks.sort(key=lambda block: block.sort_key)
    return ReportDocument(
        report_id=report_id,
        status=ReportStatus.running,
        sections=blocks,
        warnings=list(draft.warnings),
        generated_at=None,
    )


def attach_media_asset(
    report: ReportDocument,
    *,
    block_id: str,
    asset: MediaAsset,
) -> ReportDocument:
    updated_sections: list[ReportBlock] = []
    for block in report.sections:
        if block.id != block_id:
            updated_sections.append(block)
            continue
        updated_sections.append(
            block.model_copy(
                update={
                    "media": [asset],
                    "state": ReportBlockState.ready,
                }
            )
        )
    return report.model_copy(update={"sections": updated_sections})


def drop_block(report: ReportDocument, *, block_id: str, warning: str) -> ReportDocument:
    sections = [block for block in report.sections if block.id != block_id]
    warnings = [*report.warnings]
    if warning not in warnings:
        warnings.append(warning)
    return report.model_copy(update={"sections": sections, "warnings": warnings})


def finalize_report(report: ReportDocument) -> ReportDocument:
    return report.model_copy(
        update={
            "status": ReportStatus.completed,
            "generated_at": datetime.now(UTC),
        }
    )


def _draft_to_block(draft: ComposedBlockDraft) -> ReportBlock:
    return ReportBlock(
        id=draft.id,
        type=draft.type,
        title=draft.title,
        content=draft.content,
        sort_key=draft.sort_key,
        provenance=draft.provenance,
        confidence_score=draft.confidence_score,
        citations=draft.citations,
        media=[],
        state=ReportBlockState.ready,
    )


def _media_request_to_block(request: MediaRequest) -> ReportBlock:
    return ReportBlock(
        id=request.block_id,
        type=request.block_type,
        title=request.title,
        content=request.prompt or request.scene_description,
        sort_key=request.sort_key,
        provenance=(
            request.citations[0].provenance
            if request.citations
            else ReportProvenance.evidence
        ),
        confidence_score=request.confidence_score,
        citations=request.citations,
        media=[],
        state=ReportBlockState.pending,
    )
