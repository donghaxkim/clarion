from __future__ import annotations

from app.agents.reporting.types import ComposerOutput, TimelinePlan
from app.models import CaseEvidenceBundle, ReportBlockType, ReportProvenance


def validate_timeline_plan(bundle: CaseEvidenceBundle, plan: TimelinePlan) -> list[str]:
    issues: list[str] = []
    known_evidence = {item.evidence_id for item in bundle.evidence_items}
    previous_key = ""

    if not plan.timeline_events:
        issues.append("timeline plan must include at least one event")
        return issues

    for event in plan.timeline_events:
        if previous_key and event.sort_key < previous_key:
            issues.append("timeline events must be sorted by sort_key")
        previous_key = event.sort_key

        if not event.evidence_refs:
            issues.append(f"{event.event_id} is missing evidence_refs")
        missing_refs = [ref for ref in event.evidence_refs if ref not in known_evidence]
        if missing_refs:
            issues.append(f"{event.event_id} references unknown evidence ids: {missing_refs}")
        if not event.citations:
            issues.append(f"{event.event_id} is missing citations")

    return issues


def validate_composer_output(output: ComposerOutput) -> list[str]:
    issues: list[str] = []
    previous_key = ""

    if not output.blocks:
        issues.append("composer output must include at least one block")
        return issues

    for block in output.blocks:
        if previous_key and block.sort_key < previous_key:
            issues.append("report blocks must be sorted by sort_key")
        previous_key = block.sort_key

        if block.provenance == ReportProvenance.evidence and not block.citations:
            issues.append(f"{block.id} is missing evidence citations")

        for citation in block.citations:
            if citation.provenance != block.provenance:
                issues.append(
                    f"{block.id} mixes {block.provenance.value} content with "
                    f"{citation.provenance.value} citations"
                )

    return issues


def normalize_composer_output(output: ComposerOutput, timeline: TimelinePlan) -> ComposerOutput:
    event_citation_lookup = {
        event.event_id: list(event.citations) for event in timeline.timeline_events if event.citations
    }
    timeline_citations = _merge_citations(
        [event.citations for event in timeline.timeline_events if event.citations]
    )

    updated_blocks = []
    changed = False
    sorted_blocks = sorted(output.blocks, key=lambda block: block.sort_key)
    if sorted_blocks != output.blocks:
        changed = True

    for block in sorted_blocks:
        if block.provenance != ReportProvenance.evidence or block.citations:
            updated_blocks.append(block)
            continue

        citations = []
        if block.type == ReportBlockType.timeline or block.id.startswith("timeline"):
            citations = timeline_citations
        elif block.id.startswith("event-"):
            event_id = block.id.removeprefix("event-")
            citations = event_citation_lookup.get(event_id, [])

        if citations:
            changed = True
            updated_blocks.append(block.model_copy(update={"citations": citations}))
            continue

        updated_blocks.append(block)

    if not changed:
        return output
    return output.model_copy(update={"blocks": updated_blocks})


def _merge_citations(citation_groups: list[list]) -> list:
    deduped = {}
    for citations in citation_groups:
        for citation in citations:
            deduped[(citation.source_id, citation.provenance.value)] = citation
    return list(deduped.values())
