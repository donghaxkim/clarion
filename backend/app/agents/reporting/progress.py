from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from collections import deque
from typing import Any

from app.agents.reporting.types import ComposerOutput, ContextPlan, MediaPlan, TimelinePlan
from app.models import (
    ReportGenerationActivity,
    ReportGenerationActivityStatus,
    ReportGenerationPhase,
    ReportWorkflowEdge,
    ReportWorkflowEdgeRelation,
    ReportWorkflowLane,
    ReportWorkflowNode,
    ReportWorkflowNodeKind,
    ReportWorkflowNodeState,
    ReportWorkflowNodeStatus,
    ReportWorkflowState,
)

NODE_TIMELINE_PLANNER = "timeline_planner"
NODE_GROUNDING_REVIEWER = "grounding_reviewer"
NODE_TIMELINE_REFINER = "timeline_refiner"
NODE_CONTEXT_ENRICHMENT = "context_enrichment"
NODE_MEDIA_PLANNER = "media_planner"
NODE_FINAL_COMPOSER = "final_composer"
NODE_COMPOSITION_REVIEWER = "composition_reviewer"
NODE_COMPOSITION_REFINER = "composition_refiner"
NODE_IMAGE_GENERATOR = "image_generator"
NODE_RECONSTRUCTION_GENERATOR = "reconstruction_generator"
NODE_REPORT_FINALIZER = "report_finalizer"

MAX_REVIEW_ATTEMPTS = 3
MAX_COMPOSITION_REVIEW_ATTEMPTS = 2

_WORKFLOW_NODE_DEFS: tuple[
    tuple[str, str, ReportGenerationPhase, ReportWorkflowNodeKind, ReportWorkflowLane, bool],
    ...,
] = (
    (
        NODE_TIMELINE_PLANNER,
        "Building chronology outline",
        ReportGenerationPhase.timeline_planning,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.chronology,
        False,
    ),
    (
        NODE_GROUNDING_REVIEWER,
        "Checking chronology against cited evidence",
        ReportGenerationPhase.grounding_review,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.review,
        False,
    ),
    (
        NODE_TIMELINE_REFINER,
        "Repairing chronology gaps",
        ReportGenerationPhase.grounding_review,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.review,
        False,
    ),
    (
        NODE_CONTEXT_ENRICHMENT,
        "Gathering public context",
        ReportGenerationPhase.parallel_planning,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.planning,
        True,
    ),
    (
        NODE_MEDIA_PLANNER,
        "Choosing scenes for visuals",
        ReportGenerationPhase.parallel_planning,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.planning,
        False,
    ),
    (
        NODE_FINAL_COMPOSER,
        "Writing the report narrative",
        ReportGenerationPhase.composition,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.composition,
        False,
    ),
    (
        NODE_COMPOSITION_REVIEWER,
        "Reviewing the drafted report",
        ReportGenerationPhase.composition,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.composition,
        False,
    ),
    (
        NODE_COMPOSITION_REFINER,
        "Repairing drafted report prose",
        ReportGenerationPhase.composition,
        ReportWorkflowNodeKind.agent,
        ReportWorkflowLane.composition,
        False,
    ),
    (
        NODE_IMAGE_GENERATOR,
        "Rendering scene illustrations",
        ReportGenerationPhase.media_generation,
        ReportWorkflowNodeKind.worker,
        ReportWorkflowLane.media,
        True,
    ),
    (
        NODE_RECONSTRUCTION_GENERATOR,
        "Rendering reconstructions",
        ReportGenerationPhase.media_generation,
        ReportWorkflowNodeKind.worker,
        ReportWorkflowLane.media,
        True,
    ),
    (
        NODE_REPORT_FINALIZER,
        "Finalizing the report",
        ReportGenerationPhase.finalizing,
        ReportWorkflowNodeKind.worker,
        ReportWorkflowLane.finalize,
        False,
    ),
)

_WORKFLOW_EDGES = (
    (
        NODE_TIMELINE_PLANNER,
        NODE_GROUNDING_REVIEWER,
        ReportWorkflowEdgeRelation.sequence,
    ),
    (
        NODE_GROUNDING_REVIEWER,
        NODE_TIMELINE_REFINER,
        ReportWorkflowEdgeRelation.loop,
    ),
    (
        NODE_TIMELINE_REFINER,
        NODE_GROUNDING_REVIEWER,
        ReportWorkflowEdgeRelation.loop,
    ),
    (
        NODE_GROUNDING_REVIEWER,
        NODE_CONTEXT_ENRICHMENT,
        ReportWorkflowEdgeRelation.parallel,
    ),
    (
        NODE_GROUNDING_REVIEWER,
        NODE_MEDIA_PLANNER,
        ReportWorkflowEdgeRelation.parallel,
    ),
    (
        NODE_CONTEXT_ENRICHMENT,
        NODE_FINAL_COMPOSER,
        ReportWorkflowEdgeRelation.parallel,
    ),
    (
        NODE_MEDIA_PLANNER,
        NODE_FINAL_COMPOSER,
        ReportWorkflowEdgeRelation.parallel,
    ),
    (
        NODE_FINAL_COMPOSER,
        NODE_COMPOSITION_REVIEWER,
        ReportWorkflowEdgeRelation.sequence,
    ),
    (
        NODE_COMPOSITION_REVIEWER,
        NODE_COMPOSITION_REFINER,
        ReportWorkflowEdgeRelation.loop,
    ),
    (
        NODE_COMPOSITION_REFINER,
        NODE_COMPOSITION_REVIEWER,
        ReportWorkflowEdgeRelation.loop,
    ),
    (
        NODE_COMPOSITION_REVIEWER,
        NODE_IMAGE_GENERATOR,
        ReportWorkflowEdgeRelation.sequence,
    ),
    (
        NODE_COMPOSITION_REVIEWER,
        NODE_RECONSTRUCTION_GENERATOR,
        ReportWorkflowEdgeRelation.sequence,
    ),
    (
        NODE_IMAGE_GENERATOR,
        NODE_REPORT_FINALIZER,
        ReportWorkflowEdgeRelation.sequence,
    ),
    (
        NODE_RECONSTRUCTION_GENERATOR,
        NODE_REPORT_FINALIZER,
        ReportWorkflowEdgeRelation.sequence,
    ),
)

_NODE_LABELS = {node_id: label for node_id, label, *_ in _WORKFLOW_NODE_DEFS}
_NODE_PHASES = {node_id: phase for node_id, _, phase, *_ in _WORKFLOW_NODE_DEFS}
_NODE_OPTIONAL = {node_id: optional for node_id, *_, optional in _WORKFLOW_NODE_DEFS}
_NODE_ORDER = [node_id for node_id, *_ in _WORKFLOW_NODE_DEFS]
_PARALLEL_NODE_SET = {NODE_CONTEXT_ENRICHMENT, NODE_MEDIA_PLANNER}
_AGENT_NODE_MAP = {
    "TimelinePlannerAgent": NODE_TIMELINE_PLANNER,
    "GroundingReviewerAgent": NODE_GROUNDING_REVIEWER,
    "TimelineRefinerAgent": NODE_TIMELINE_REFINER,
    "ContextEnrichmentAgent": NODE_CONTEXT_ENRICHMENT,
    "MediaPlannerAgent": NODE_MEDIA_PLANNER,
    "FinalComposerAgent": NODE_FINAL_COMPOSER,
    "CompositionReviewerAgent": NODE_COMPOSITION_REVIEWER,
    "CompositionRefinerAgent": NODE_COMPOSITION_REFINER,
}


@dataclass(slots=True)
class PipelinePreviewSnapshot:
    timeline_plan: TimelinePlan | None = None
    context_plan: ContextPlan | None = None
    media_plan: MediaPlan | None = None
    composer_output: ComposerOutput | None = None

    def copy(self) -> PipelinePreviewSnapshot:
        return PipelinePreviewSnapshot(
            timeline_plan=self.timeline_plan,
            context_plan=self.context_plan,
            media_plan=self.media_plan,
            composer_output=self.composer_output,
        )


@dataclass(slots=True)
class PipelineProgressEvent:
    kind: str
    node_id: str | None = None
    detail: str | None = None
    attempt: int | None = None
    snapshot: PipelinePreviewSnapshot | None = None
    preview_reason: str | None = None

    @classmethod
    def node_started(
        cls,
        node_id: str,
        *,
        detail: str | None = None,
        attempt: int | None = None,
    ) -> PipelineProgressEvent:
        return cls(
            kind="node_started",
            node_id=node_id,
            detail=detail,
            attempt=attempt,
        )

    @classmethod
    def node_completed(
        cls,
        node_id: str,
        *,
        detail: str | None = None,
        attempt: int | None = None,
    ) -> PipelineProgressEvent:
        return cls(
            kind="node_completed",
            node_id=node_id,
            detail=detail,
            attempt=attempt,
        )

    @classmethod
    def node_failed(
        cls,
        node_id: str,
        *,
        detail: str | None = None,
        attempt: int | None = None,
    ) -> PipelineProgressEvent:
        return cls(
            kind="node_failed",
            node_id=node_id,
            detail=detail,
            attempt=attempt,
        )

    @classmethod
    def node_detail(
        cls,
        node_id: str,
        *,
        detail: str,
        attempt: int | None = None,
    ) -> PipelineProgressEvent:
        return cls(
            kind="node_detail",
            node_id=node_id,
            detail=detail,
            attempt=attempt,
        )

    @classmethod
    def snapshot_updated(
        cls,
        snapshot: PipelinePreviewSnapshot,
        *,
        preview_reason: str,
    ) -> PipelineProgressEvent:
        return cls(
            kind="snapshot",
            snapshot=snapshot,
            preview_reason=preview_reason,
        )


class ProgressEventBuffer:
    def __init__(self) -> None:
        self._events: deque[PipelineProgressEvent] = deque()
        self._review_attempt = 0
        self._composition_review_attempt = 0

    def emit(self, event: PipelineProgressEvent) -> None:
        self._events.append(event)

    def drain(self) -> list[PipelineProgressEvent]:
        drained = list(self._events)
        self._events.clear()
        return drained

    def agent_started(self, agent_name: str) -> None:
        node_id = _AGENT_NODE_MAP.get(agent_name)
        if node_id is None:
            return
        detail, attempt = self._agent_detail(node_id, increment_review=True)
        self.emit(
            PipelineProgressEvent.node_started(
                node_id,
                detail=detail,
                attempt=attempt,
            )
        )

    def agent_completed(self, agent_name: str) -> None:
        node_id = _AGENT_NODE_MAP.get(agent_name)
        if node_id is None:
            return
        detail, attempt = self._agent_detail(node_id)
        self.emit(
            PipelineProgressEvent.node_completed(
                node_id,
                detail=detail,
                attempt=attempt,
            )
        )

    def agent_failed(self, agent_name: str, error: str) -> None:
        node_id = _AGENT_NODE_MAP.get(agent_name)
        if node_id is None:
            return
        detail, attempt = self._agent_detail(node_id, fallback_detail=error)
        self.emit(
            PipelineProgressEvent.node_failed(
                node_id,
                detail=detail,
                attempt=attempt,
            )
        )

    def tool_started(self, agent_name: str, tool_name: str, args: dict[str, Any]) -> None:
        node_id = _AGENT_NODE_MAP.get(agent_name)
        if node_id != NODE_CONTEXT_ENRICHMENT:
            return
        detail = _format_tool_detail(tool_name, args)
        if detail:
            self.emit(PipelineProgressEvent.node_detail(node_id, detail=detail))

    def tool_failed(self, agent_name: str, tool_name: str, error: str) -> None:
        node_id = _AGENT_NODE_MAP.get(agent_name)
        if node_id != NODE_CONTEXT_ENRICHMENT:
            return
        self.emit(
            PipelineProgressEvent.node_detail(
                node_id,
                detail=f"{tool_name} failed: {error}",
            )
        )

    def _agent_detail(
        self,
        node_id: str,
        *,
        increment_review: bool = False,
        fallback_detail: str | None = None,
    ) -> tuple[str | None, int | None]:
        if node_id == NODE_GROUNDING_REVIEWER:
            if increment_review:
                self._review_attempt += 1
            attempt = self._review_attempt
            return f"Review pass {attempt} of {MAX_REVIEW_ATTEMPTS}", attempt
        if node_id == NODE_TIMELINE_REFINER:
            attempt = max(self._review_attempt, 1)
            return f"Review pass {attempt} of {MAX_REVIEW_ATTEMPTS}", attempt
        if node_id == NODE_COMPOSITION_REVIEWER:
            if increment_review:
                self._composition_review_attempt += 1
            attempt = max(self._composition_review_attempt, 1)
            return (
                f"Draft review pass {attempt} of {MAX_COMPOSITION_REVIEW_ATTEMPTS}",
                attempt,
            )
        if node_id == NODE_COMPOSITION_REFINER:
            attempt = max(self._composition_review_attempt, 1)
            return (
                f"Draft review pass {attempt} of {MAX_COMPOSITION_REVIEW_ATTEMPTS}",
                attempt,
            )
        return fallback_detail, None


def build_workflow_state(*, enable_public_context: bool) -> ReportWorkflowState:
    nodes = [
        ReportWorkflowNode(
            node_id=node_id,
            label=label,
            kind=kind,
            lane=lane,
            optional=optional,
        )
        for node_id, label, _phase, kind, lane, optional in _WORKFLOW_NODE_DEFS
    ]
    node_states = [
        ReportWorkflowNodeState(
            node_id=node.node_id,
            status=(
                ReportWorkflowNodeStatus.skipped
                if node.node_id == NODE_CONTEXT_ENRICHMENT and not enable_public_context
                else ReportWorkflowNodeStatus.pending
            ),
        )
        for node in nodes
    ]
    edges = [
        ReportWorkflowEdge(
            source_node_id=source,
            target_node_id=target,
            relation=relation,
        )
        for source, target, relation in _WORKFLOW_EDGES
    ]
    return ReportWorkflowState(nodes=nodes, edges=edges, node_states=node_states)


def build_queued_activity() -> ReportGenerationActivity:
    return ReportGenerationActivity(
        phase=ReportGenerationPhase.queued,
        status=ReportGenerationActivityStatus.running,
        label="Waiting to start report generation.",
        updated_at=datetime.now(UTC),
    )


class WorkflowProgressTracker:
    def __init__(self, workflow: ReportWorkflowState):
        self._nodes = {node.node_id: node for node in workflow.nodes}
        self._node_states = {state.node_id: state for state in workflow.node_states}
        self._active_node_ids = list(workflow.active_node_ids)
        self._workflow = workflow
        self._activity: ReportGenerationActivity | None = None

    @property
    def workflow(self) -> ReportWorkflowState:
        return self._workflow

    @property
    def activity(self) -> ReportGenerationActivity | None:
        return self._activity

    @property
    def active_node_ids(self) -> list[str]:
        return list(self._active_node_ids)

    def apply_event(
        self,
        event: PipelineProgressEvent,
        *,
        now: datetime | None = None,
    ) -> tuple[ReportWorkflowState, ReportGenerationActivity | None, list[str]]:
        timestamp = now or datetime.now(UTC)
        changed_node_ids: list[str] = []

        if event.kind == "snapshot" and event.snapshot is not None:
            changed_node_ids.extend(
                self._sync_media_nodes(event.snapshot.media_plan, timestamp=timestamp)
            )
        elif event.node_id is not None and event.node_id in self._node_states:
            transition = event.kind
            if transition == "node_started":
                changed_node_ids.extend(
                    self._start_node(
                        event.node_id,
                        timestamp=timestamp,
                        detail=event.detail,
                        attempt=event.attempt,
                    )
                )
            elif transition == "node_completed":
                changed_node_ids.extend(
                    self._complete_node(
                        event.node_id,
                        timestamp=timestamp,
                        detail=event.detail,
                        attempt=event.attempt,
                    )
                )
            elif transition == "node_failed":
                changed_node_ids.extend(
                    self._fail_node(
                        event.node_id,
                        timestamp=timestamp,
                        detail=event.detail,
                        attempt=event.attempt,
                    )
                )
            elif transition == "node_detail":
                changed_node_ids.extend(
                    self._update_detail(
                        event.node_id,
                        detail=event.detail,
                        attempt=event.attempt,
                    )
                )

        self._workflow = self._workflow.model_copy(
            update={
                "node_states": [self._node_states[node_id] for node_id in _NODE_ORDER],
                "active_node_ids": list(self._active_node_ids),
            }
        )
        self._activity = self._build_activity(event, timestamp=timestamp)
        return self._workflow, self._activity, changed_node_ids

    def _start_node(
        self,
        node_id: str,
        *,
        timestamp: datetime,
        detail: str | None,
        attempt: int | None,
    ) -> list[str]:
        state = self._node_states[node_id]
        self._node_states[node_id] = state.model_copy(
            update={
                "status": ReportWorkflowNodeStatus.running,
                "detail": detail,
                "attempt": attempt,
                "started_at": timestamp,
                "completed_at": None,
            }
        )
        if node_id not in self._active_node_ids:
            self._active_node_ids.append(node_id)
        return [node_id]

    def _complete_node(
        self,
        node_id: str,
        *,
        timestamp: datetime,
        detail: str | None,
        attempt: int | None,
    ) -> list[str]:
        state = self._node_states[node_id]
        self._node_states[node_id] = state.model_copy(
            update={
                "status": ReportWorkflowNodeStatus.completed,
                "detail": detail if detail is not None else state.detail,
                "attempt": attempt if attempt is not None else state.attempt,
                "completed_at": timestamp,
                "started_at": state.started_at or timestamp,
            }
        )
        self._active_node_ids = [active for active in self._active_node_ids if active != node_id]
        return [node_id]

    def _fail_node(
        self,
        node_id: str,
        *,
        timestamp: datetime,
        detail: str | None,
        attempt: int | None,
    ) -> list[str]:
        state = self._node_states[node_id]
        self._node_states[node_id] = state.model_copy(
            update={
                "status": ReportWorkflowNodeStatus.failed,
                "detail": detail if detail is not None else state.detail,
                "attempt": attempt if attempt is not None else state.attempt,
                "completed_at": timestamp,
                "started_at": state.started_at or timestamp,
            }
        )
        self._active_node_ids = [active for active in self._active_node_ids if active != node_id]
        return [node_id]

    def _update_detail(
        self,
        node_id: str,
        *,
        detail: str | None,
        attempt: int | None,
    ) -> list[str]:
        state = self._node_states[node_id]
        self._node_states[node_id] = state.model_copy(
            update={
                "detail": detail if detail is not None else state.detail,
                "attempt": attempt if attempt is not None else state.attempt,
            }
        )
        return [node_id]

    def _sync_media_nodes(
        self,
        media_plan: MediaPlan | None,
        *,
        timestamp: datetime,
    ) -> list[str]:
        if media_plan is None:
            return []

        changed_node_ids: list[str] = []
        if not media_plan.image_requests:
            changed_node_ids.extend(
                self._mark_node_skipped(NODE_IMAGE_GENERATOR, timestamp=timestamp)
            )
        if not media_plan.reconstruction_requests:
            changed_node_ids.extend(
                self._mark_node_skipped(
                    NODE_RECONSTRUCTION_GENERATOR,
                    timestamp=timestamp,
                )
            )
        return changed_node_ids

    def _mark_node_skipped(self, node_id: str, *, timestamp: datetime) -> list[str]:
        state = self._node_states[node_id]
        if state.status != ReportWorkflowNodeStatus.pending:
            return []
        self._node_states[node_id] = state.model_copy(
            update={
                "status": ReportWorkflowNodeStatus.skipped,
                "completed_at": timestamp,
            }
        )
        return [node_id]

    def _build_activity(
        self,
        event: PipelineProgressEvent,
        *,
        timestamp: datetime,
    ) -> ReportGenerationActivity | None:
        if event.kind == "node_failed" and event.node_id is not None:
            return self._activity_for_single_node(
                event.node_id,
                status=ReportGenerationActivityStatus.failed,
                timestamp=timestamp,
            )

        if self._active_node_ids:
            active_set = set(self._active_node_ids)
            if active_set == _PARALLEL_NODE_SET:
                return ReportGenerationActivity(
                    phase=ReportGenerationPhase.parallel_planning,
                    status=ReportGenerationActivityStatus.running,
                    label="Planning context notes and visuals in parallel.",
                    detail=self._parallel_detail(),
                    active_node_ids=list(self._active_node_ids),
                    updated_at=timestamp,
                )

            return self._activity_for_single_node(
                self._active_node_ids[0],
                status=ReportGenerationActivityStatus.running,
                timestamp=timestamp,
            )

        if event.node_id is None:
            return self._activity

        if event.kind == "node_completed":
            return self._activity_for_single_node(
                event.node_id,
                status=ReportGenerationActivityStatus.completed,
                timestamp=timestamp,
            )

        if event.kind == "node_detail" and self._activity is not None:
            return self._activity.model_copy(
                update={
                    "detail": self._node_states.get(event.node_id, self._node_states[_NODE_ORDER[0]]).detail
                    if event.node_id is not None
                    else self._activity.detail,
                    "updated_at": timestamp,
                }
            )

        return self._activity

    def _activity_for_single_node(
        self,
        node_id: str,
        *,
        status: ReportGenerationActivityStatus,
        timestamp: datetime,
    ) -> ReportGenerationActivity:
        state = self._node_states[node_id]
        max_attempts = MAX_REVIEW_ATTEMPTS if node_id in {
            NODE_GROUNDING_REVIEWER,
            NODE_TIMELINE_REFINER,
        } else (
            MAX_COMPOSITION_REVIEW_ATTEMPTS
            if node_id in {NODE_COMPOSITION_REVIEWER, NODE_COMPOSITION_REFINER}
            else None
        )
        return ReportGenerationActivity(
            phase=_NODE_PHASES[node_id],
            status=status,
            label=_NODE_LABELS[node_id],
            detail=state.detail,
            node_id=node_id,
            active_node_ids=list(self._active_node_ids),
            attempt=state.attempt,
            max_attempts=max_attempts,
            updated_at=timestamp,
        )

    def _parallel_detail(self) -> str | None:
        details = [
            state.detail or _NODE_LABELS[node_id]
            for node_id in self._active_node_ids
            for state in [self._node_states[node_id]]
        ]
        compact = [detail for detail in details if detail]
        return " | ".join(compact) if compact else None


def _format_tool_detail(tool_name: str, args: dict[str, Any]) -> str | None:
    query = args.get("query") or args.get("q")
    if isinstance(query, str) and query.strip():
        return f"Searching public context: {query.strip()}"
    return f"Running {tool_name}."
