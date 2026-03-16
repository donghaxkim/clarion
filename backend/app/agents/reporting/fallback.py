from __future__ import annotations

import inspect
from typing import Awaitable, Callable

from app.agents.reporting.progress import (
    NODE_CONTEXT_ENRICHMENT,
    NODE_FINAL_COMPOSER,
    NODE_GROUNDING_REVIEWER,
    NODE_MEDIA_PLANNER,
    NODE_TIMELINE_PLANNER,
    PipelinePreviewSnapshot,
    PipelineProgressEvent,
)
from app.agents.reporting.types import (
    ComposerOutput,
    ComposedBlockDraft,
    ContextNote,
    ContextPlan,
    MediaPlan,
    MediaRequest,
    PipelineResult,
    ReportGenerationPolicy,
    TimelineEvent,
    TimelinePlan,
)
from app.agents.reporting.validators import normalize_media_plan, validate_timeline_plan
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EventCandidate,
    ReportBlockType,
    ReportProvenance,
)
from app.services.generation.report_citations import (
    build_evidence_citation,
    build_public_context_citation,
)

ProgressCallback = Callable[[PipelineProgressEvent], Awaitable[None] | None]


class HeuristicReportingPipeline:
    DEFAULT_WARNING_MESSAGE = (
        "ADK runtime unavailable or not configured; used deterministic fallback pipeline."
    )

    def __init__(
        self,
        policy: ReportGenerationPolicy,
        *,
        warning_message: str | None = None,
    ):
        self.policy = policy
        self.warning_message = warning_message or self.DEFAULT_WARNING_MESSAGE

    async def run(
        self,
        *,
        bundle: CaseEvidenceBundle,
        report_id: str,
        user_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        del report_id, user_id
        preview_snapshot = PipelinePreviewSnapshot()

        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_started(NODE_TIMELINE_PLANNER),
        )
        timeline = self._build_timeline(bundle)
        preview_snapshot.timeline_plan = timeline
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.snapshot_updated(
                preview_snapshot.copy(),
                preview_reason="timeline_plan",
            ),
        )
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_completed(NODE_TIMELINE_PLANNER),
        )

        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_started(
                NODE_GROUNDING_REVIEWER,
                detail="Review pass 1 of 3",
                attempt=1,
            ),
        )
        issues = validate_timeline_plan(bundle, timeline)
        if issues:
            await _emit_progress(
                progress_callback,
                PipelineProgressEvent.node_failed(
                    NODE_GROUNDING_REVIEWER,
                    detail="; ".join(issues),
                    attempt=1,
                ),
            )
            raise ValueError("; ".join(issues))
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_completed(
                NODE_GROUNDING_REVIEWER,
                detail="Review pass 1 of 3",
                attempt=1,
            ),
        )

        if self.policy.enable_public_context:
            await _emit_progress(
                progress_callback,
                PipelineProgressEvent.node_started(NODE_CONTEXT_ENRICHMENT),
            )
        context_notes = self._build_context_notes(timeline)
        preview_snapshot.context_plan = ContextPlan(notes=context_notes)
        if self.policy.enable_public_context:
            await _emit_progress(
                progress_callback,
                PipelineProgressEvent.snapshot_updated(
                    preview_snapshot.copy(),
                    preview_reason="context_plan",
                ),
            )
            await _emit_progress(
                progress_callback,
                PipelineProgressEvent.node_completed(NODE_CONTEXT_ENRICHMENT),
            )

        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_started(NODE_MEDIA_PLANNER),
        )
        blocks = self._build_blocks(timeline, context_notes)
        image_requests, reconstruction_requests = self._build_media_plans(blocks, timeline)
        preview_snapshot.media_plan = MediaPlan(
            image_requests=image_requests,
            reconstruction_requests=reconstruction_requests,
        )
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.snapshot_updated(
                preview_snapshot.copy(),
                preview_reason="media_plan",
            ),
        )
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_completed(NODE_MEDIA_PLANNER),
        )

        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_started(NODE_FINAL_COMPOSER),
        )
        preview_snapshot.composer_output = ComposerOutput(blocks=blocks)
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.snapshot_updated(
                preview_snapshot.copy(),
                preview_reason="composer_output",
            ),
        )
        await _emit_progress(
            progress_callback,
            PipelineProgressEvent.node_completed(NODE_FINAL_COMPOSER),
        )
        return PipelineResult(
            blocks=blocks,
            image_requests=image_requests,
            reconstruction_requests=reconstruction_requests,
            warnings=[self.warning_message],
        )

    def _build_timeline(self, bundle: CaseEvidenceBundle) -> TimelinePlan:
        candidates = sorted(bundle.event_candidates, key=lambda item: item.sort_key)
        if candidates:
            events = [self._event_from_candidate(candidate, bundle) for candidate in candidates]
            return TimelinePlan(timeline_events=events)

        events: list[TimelineEvent] = []
        for index, evidence in enumerate(bundle.evidence_items, start=1):
            summary = evidence.summary or evidence.extracted_text or evidence.title or evidence.evidence_id
            title = evidence.title or f"Evidence Event {index}"
            events.append(
                TimelineEvent(
                    event_id=f"derived-{index}",
                    title=title,
                    narrative=summary.strip(),
                    sort_key=f"{index:04d}",
                    evidence_refs=[evidence.evidence_id],
                    citations=[_citation_from_evidence(evidence.evidence_id, bundle=bundle)],
                    confidence_score=evidence.confidence_score,
                    # Derived evidence-only events are too underspecified for safe media planning.
                    scene_description=None,
                    image_prompt=None,
                )
            )
        return TimelinePlan(timeline_events=events)

    def _event_from_candidate(
        self,
        candidate: EventCandidate,
        bundle: CaseEvidenceBundle,
    ) -> TimelineEvent:
        citations = list(candidate.citations)
        if not citations:
            citations = [_citation_from_evidence(ref, bundle=bundle) for ref in candidate.evidence_refs]
        if not citations:
            evidence = bundle.evidence_items[0]
            citations = [_citation_from_evidence(evidence.evidence_id, bundle=bundle)]

        return TimelineEvent(
            event_id=candidate.event_id,
            title=candidate.title,
            narrative=candidate.description,
            sort_key=candidate.sort_key,
            timestamp_label=candidate.timestamp_label,
            evidence_refs=candidate.evidence_refs or [citations[0].source_id],
            citations=citations,
            scene_description=candidate.scene_description,
            image_prompt=candidate.image_prompt_hint,
            reference_image_uris=candidate.reference_image_uris,
            public_context_queries=candidate.public_context_queries,
            confidence_score=0.72,
        )

    def _build_context_notes(self, timeline: TimelinePlan) -> list[ContextNote]:
        if not self.policy.enable_public_context:
            return []

        notes: list[ContextNote] = []
        for event in timeline.timeline_events:
            if not event.public_context_queries:
                continue
            query_summary = ", ".join(event.public_context_queries)
            note_content = (
                "Live public-context grounding is enabled for this event. "
                f"Suggested enrichment queries: {query_summary}."
            )
            notes.append(
                ContextNote(
                    title=f"Context for {event.title}",
                    content=note_content,
                    sort_key=f"{event.sort_key}-ctx",
                    citations=[
                        build_public_context_citation(
                            query,
                            fallback_excerpt=note_content,
                        )
                        for query in event.public_context_queries
                    ],
                    confidence_score=0.35,
                )
            )
        return notes

    def _build_blocks(
        self,
        timeline: TimelinePlan,
        context_notes: list[ContextNote],
    ) -> list[ComposedBlockDraft]:
        blocks: list[ComposedBlockDraft] = []
        for event in timeline.timeline_events:
            blocks.append(
                ComposedBlockDraft(
                    id=f"event-{event.event_id}",
                    type=ReportBlockType.text,
                    title=event.title,
                    content=event.narrative,
                    sort_key=event.sort_key,
                    provenance=ReportProvenance.evidence,
                    confidence_score=event.confidence_score or 0.7,
                    citations=event.citations,
                )
            )

        for index, note in enumerate(context_notes, start=1):
            blocks.append(
                ComposedBlockDraft(
                    id=f"context-{index}",
                    type=ReportBlockType.text,
                    title=note.title,
                    content=note.content,
                    sort_key=note.sort_key,
                    provenance=ReportProvenance.public_context,
                    confidence_score=note.confidence_score,
                    citations=note.citations,
                )
            )

        return sorted(blocks, key=lambda block: block.sort_key)

    def _build_media_plans(
        self,
        blocks: list[ComposedBlockDraft],
        timeline: TimelinePlan,
    ) -> tuple[list[MediaRequest], list[MediaRequest]]:
        image_requests: list[MediaRequest] = []
        reconstruction_requests: list[MediaRequest] = []
        block_lookup = {block.id: block for block in blocks}

        for event in timeline.timeline_events:
            anchor_id = f"event-{event.event_id}"
            block = block_lookup.get(anchor_id)
            if block is None:
                continue

            if event.image_prompt and len(image_requests) < self.policy.max_images:
                image_requests.append(
                    MediaRequest(
                        block_id=f"{anchor_id}-image",
                        block_type=ReportBlockType.image,
                        anchor_block_id=anchor_id,
                        title=f"Scene Illustration: {event.title}",
                        sort_key=f"{block.sort_key}.10",
                        citations=event.citations,
                        confidence_score=block.confidence_score,
                        prompt=event.image_prompt,
                        evidence_refs=event.evidence_refs,
                        reference_image_uris=event.reference_image_uris,
                    )
                )

            if event.scene_description and len(reconstruction_requests) < self.policy.max_reconstructions:
                reconstruction_requests.append(
                    MediaRequest(
                        block_id=f"{anchor_id}-video",
                        block_type=ReportBlockType.video,
                        anchor_block_id=anchor_id,
                        title=f"Reconstruction: {event.title}",
                        sort_key=f"{block.sort_key}.20",
                        citations=event.citations,
                        confidence_score=block.confidence_score,
                        scene_description=event.scene_description,
                        evidence_refs=event.evidence_refs,
                        reference_image_uris=event.reference_image_uris,
                    )
                )

        media_plan = normalize_media_plan(
            MediaPlan(
                image_requests=image_requests,
                reconstruction_requests=reconstruction_requests,
            ),
            timeline,
        )
        return media_plan.image_requests, media_plan.reconstruction_requests


def _citation_from_evidence(
    evidence_id: str,
    *,
    bundle: CaseEvidenceBundle | None = None,
) -> Citation:
    evidence = None
    if bundle is not None:
        evidence = next(
            (item for item in bundle.evidence_items if item.evidence_id == evidence_id),
            None,
        )
    citation = build_evidence_citation(
        evidence_id,
        bundle=bundle,
        source_label=(evidence.title if evidence is not None else None),
        allow_document_excerpt=True,
    )
    if citation is None:
        raise ValueError(f"Unable to build evidence citation for {evidence_id}")
    return citation


async def _emit_progress(
    progress_callback: ProgressCallback | None,
    event: PipelineProgressEvent,
) -> None:
    if progress_callback is None:
        return
    result = progress_callback(event)
    if inspect.isawaitable(result):
        await result
