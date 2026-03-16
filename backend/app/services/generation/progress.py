from __future__ import annotations

from app.agents.reporting.progress import (
    MAX_REVIEW_ATTEMPTS,
    NODE_CONTEXT_ENRICHMENT,
    NODE_FINAL_COMPOSER,
    NODE_GROUNDING_REVIEWER,
    NODE_MEDIA_PLANNER,
    NODE_TIMELINE_PLANNER,
    NODE_TIMELINE_REFINER,
    PipelineProgressEvent,
)

_REVIEWER_PROGRESS_BY_ATTEMPT = {
    1: 28,
    2: 34,
    3: 38,
}
_REFINER_PROGRESS_BY_ATTEMPT = {
    1: 32,
    2: 36,
    3: 40,
}


class ReportProgressPolicy:
    queued = 0
    intake_started = 5
    timeline_planning_started = 10
    timeline_preview_ready = 22
    parallel_planning_started = 40
    context_preview_ready = 52
    media_plan_ready = 60
    composition_started = 68
    composer_preview_ready = 78
    timeline_ready = 80
    media_complete_floor = 80
    media_complete_ceiling = 95
    finalizing_started = 97
    finalizing_ready = 99
    completed = 100

    def progress_for_pipeline_event(self, event: PipelineProgressEvent) -> int | None:
        if event.preview_reason == "timeline_plan":
            return self.timeline_preview_ready
        if event.preview_reason == "context_plan":
            return self.context_preview_ready
        if event.preview_reason == "media_plan":
            return self.media_plan_ready
        if event.preview_reason == "composer_output":
            return self.composer_preview_ready

        if event.kind != "node_started" or event.node_id is None:
            return None

        if event.node_id == NODE_TIMELINE_PLANNER:
            return self.timeline_planning_started
        if event.node_id == NODE_GROUNDING_REVIEWER:
            return _progress_for_review_attempt(
                _REVIEWER_PROGRESS_BY_ATTEMPT,
                attempt=event.attempt,
            )
        if event.node_id == NODE_TIMELINE_REFINER:
            return _progress_for_review_attempt(
                _REFINER_PROGRESS_BY_ATTEMPT,
                attempt=event.attempt,
            )
        if event.node_id in {NODE_CONTEXT_ENRICHMENT, NODE_MEDIA_PLANNER}:
            return self.parallel_planning_started
        if event.node_id == NODE_FINAL_COMPOSER:
            return self.composition_started
        return None

    def progress_for_media_processed(
        self,
        *,
        processed_count: int,
        total_count: int,
    ) -> int | None:
        if total_count <= 0:
            return None

        clamped_processed = max(0, min(processed_count, total_count))
        return self.media_complete_floor + int(
            (self.media_complete_ceiling - self.media_complete_floor)
            * clamped_processed
            / total_count
        )


def _progress_for_review_attempt(
    by_attempt: dict[int, int],
    *,
    attempt: int | None,
) -> int:
    bounded_attempt = max(1, min(MAX_REVIEW_ATTEMPTS, attempt or 1))
    return by_attempt[bounded_attempt]
