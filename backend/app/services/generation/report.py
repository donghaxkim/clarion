from __future__ import annotations

from datetime import UTC, datetime

from app.agents.reporting.progress import PipelinePreviewSnapshot
from app.agents.reporting.types import (
    ComposedBlockDraft,
    MediaPlan,
    MediaRequest,
    PipelineResult,
)
from app.models import (
    CaseEvidenceBundle,
    MediaAsset,
    ReportBlock,
    ReportBlockState,
    ReportBlockType,
    ReportDocument,
    ReportProvenance,
    ReportStatus,
)
from app.services.generation.report_citations import normalize_report_document


def create_initial_report(
    report_id: str,
    draft: PipelineResult,
    *,
    bundle: CaseEvidenceBundle | None = None,
) -> ReportDocument:
    normalized_draft = _normalize_pipeline_result(draft)
    blocks = [_draft_to_block(block) for block in normalized_draft.blocks]
    blocks.extend(_media_request_to_block(request) for request in normalized_draft.image_requests)
    blocks.extend(
        _media_request_to_block(request)
        for request in normalized_draft.reconstruction_requests
    )
    blocks.sort(key=lambda block: block.sort_key)
    report = ReportDocument(
        report_id=report_id,
        status=ReportStatus.running,
        sections=blocks,
        warnings=list(draft.warnings),
        generated_at=None,
    )
    return normalize_report_document(report, bundle=bundle)[0]


def create_preview_report(
    report_id: str,
    *,
    snapshot: PipelinePreviewSnapshot,
    warnings: list[str] | None = None,
    bundle: CaseEvidenceBundle | None = None,
) -> ReportDocument:
    media_plan = _normalize_media_plan(snapshot.media_plan)
    blocks: list[ReportBlock] = []

    if snapshot.composer_output is not None:
        blocks.extend(_draft_to_block(block) for block in snapshot.composer_output.blocks)
    elif snapshot.timeline_plan is not None:
        blocks.extend(_timeline_plan_to_preview_blocks(snapshot.timeline_plan))
        blocks.extend(_context_plan_to_preview_blocks(snapshot.context_plan))

    if media_plan is not None:
        blocks.extend(_media_request_to_block(request) for request in media_plan.image_requests)
        blocks.extend(
            _media_request_to_block(request)
            for request in media_plan.reconstruction_requests
        )

    blocks.sort(key=lambda block: block.sort_key)
    report = ReportDocument(
        report_id=report_id,
        status=ReportStatus.running,
        sections=blocks,
        warnings=list(warnings or []),
        generated_at=None,
    )
    return normalize_report_document(report, bundle=bundle)[0]


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


def _timeline_plan_to_preview_blocks(snapshot) -> list[ReportBlock]:
    blocks = []
    for event in snapshot.timeline_events:
        blocks.append(
            ReportBlock(
                id=f"event-{event.event_id}",
                type=ReportBlockType.text,
                title=event.title,
                content=event.narrative,
                sort_key=event.sort_key,
                provenance=ReportProvenance.evidence,
                confidence_score=event.confidence_score or 0.7,
                citations=event.citations,
                media=[],
                state=ReportBlockState.pending,
            )
        )
    return blocks


def _context_plan_to_preview_blocks(snapshot) -> list[ReportBlock]:
    if snapshot is None:
        return []

    return [
        ReportBlock(
            id=f"context-{index}",
            type=ReportBlockType.text,
            title=note.title,
            content=note.content,
            sort_key=note.sort_key,
            provenance=ReportProvenance.public_context,
            confidence_score=note.confidence_score,
            citations=note.citations,
            media=[],
            state=ReportBlockState.pending,
        )
        for index, note in enumerate(snapshot.notes, start=1)
    ]


def _normalize_pipeline_result(draft: PipelineResult | object) -> PipelineResult:
    if isinstance(draft, PipelineResult):
        return PipelineResult.model_validate(draft.model_dump(mode="json"))
    return PipelineResult.model_validate(draft)


def _normalize_media_plan(media_plan: MediaPlan | object | None) -> MediaPlan | None:
    if media_plan is None:
        return None
    if isinstance(media_plan, MediaPlan):
        return MediaPlan.model_validate(media_plan.model_dump(mode="json"))
    return MediaPlan.model_validate(media_plan)
