from app.agents.reporting.progress import (
    NODE_CONTEXT_ENRICHMENT,
    NODE_FINAL_COMPOSER,
    NODE_GROUNDING_REVIEWER,
    NODE_TIMELINE_PLANNER,
    NODE_TIMELINE_REFINER,
    PipelinePreviewSnapshot,
    PipelineProgressEvent,
)
from app.services.generation.progress import ReportProgressPolicy


def test_progress_policy_assigns_pipeline_milestones():
    policy = ReportProgressPolicy()

    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_started(NODE_TIMELINE_PLANNER)
        )
        == 10
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.snapshot_updated(
                PipelinePreviewSnapshot(),
                preview_reason="timeline_plan",
            )
        )
        == 22
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_started(
                NODE_GROUNDING_REVIEWER,
                attempt=1,
            )
        )
        == 28
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_started(
                NODE_TIMELINE_REFINER,
                attempt=2,
            )
        )
        == 36
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_started(NODE_CONTEXT_ENRICHMENT)
        )
        == 40
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.snapshot_updated(
                PipelinePreviewSnapshot(),
                preview_reason="context_plan",
            )
        )
        == 52
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_started(NODE_FINAL_COMPOSER)
        )
        == 68
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.snapshot_updated(
                PipelinePreviewSnapshot(),
                preview_reason="composer_output",
            )
        )
        == 78
    )
    assert (
        policy.progress_for_pipeline_event(
            PipelineProgressEvent.node_completed(NODE_TIMELINE_PLANNER)
        )
        is None
    )


def test_progress_policy_maps_media_completion_into_monotonic_band():
    policy = ReportProgressPolicy()

    assert policy.progress_for_media_processed(processed_count=1, total_count=1) == 95
    assert policy.progress_for_media_processed(processed_count=1, total_count=2) == 87
    assert policy.progress_for_media_processed(processed_count=2, total_count=2) == 95
    assert policy.progress_for_media_processed(processed_count=1, total_count=3) == 85
    assert policy.progress_for_media_processed(processed_count=2, total_count=3) == 90
    assert policy.progress_for_media_processed(processed_count=3, total_count=3) == 95
