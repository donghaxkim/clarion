import pytest
from pydantic import ValidationError

from app.agents.reporting.types import ComposerOutput, MediaPlan, PipelineResult, TimelinePlan
from app.agents.reporting.validators import normalize_composer_output, validate_composer_output
from app.models import (
    CaseEvidenceBundle,
    Citation,
    EvidenceItem,
    EvidenceItemType,
    GenerateReportRequest,
    ReportBlock,
    ReportBlockState,
    ReportBlockType,
    ReportDocument,
    ReportProvenance,
    ReportStatus,
    SourceSpan,
)


def test_case_bundle_requires_evidence_items():
    with pytest.raises(ValidationError):
        CaseEvidenceBundle(case_id="case-1", evidence_items=[])


def test_source_span_rejects_inverted_time_ranges():
    with pytest.raises(ValidationError):
        SourceSpan(time_range_ms=(2000, 1000))


def test_source_span_accepts_tuple_input_and_normalizes_to_list():
    span = SourceSpan(time_range_ms=(1000, 2000))
    assert span.time_range_ms == [1000, 2000]


def test_timeline_plan_schema_does_not_emit_prefix_items_for_time_ranges():
    schema = TimelinePlan.model_json_schema()
    time_range_schema = schema["$defs"]["Citation"]["properties"]["time_range_ms"]
    assert "prefixItems" not in time_range_schema
    array_variant = next(
        variant for variant in time_range_schema["anyOf"] if variant.get("type") == "array"
    )
    assert array_variant["items"] == {"type": "integer"}
    assert array_variant["minItems"] == 2
    assert array_variant["maxItems"] == 2


def test_adk_can_build_output_schema_tools_for_reporting_models():
    google_adk = pytest.importorskip("google.adk")
    assert google_adk is not None

    from google.adk.tools.set_model_response_tool import SetModelResponseTool

    assert SetModelResponseTool(TimelinePlan)._get_declaration() is not None
    assert SetModelResponseTool(MediaPlan)._get_declaration() is not None
    assert SetModelResponseTool(ComposerOutput)._get_declaration() is not None


def test_composer_output_normalization_backfills_event_citations():
    citation = Citation(
        source_id="ev-1",
        segment_id="seg-1",
        excerpt="Collision occurs in the intersection.",
        provenance=ReportProvenance.evidence,
    )
    timeline = TimelinePlan(
        timeline_events=[
            {
                "event_id": "impact",
                "title": "Impact",
                "narrative": "Collision occurs.",
                "sort_key": "0001",
                "evidence_refs": ["ev-1"],
                "citations": [citation.model_dump(mode="json")],
            }
        ]
    )
    output = ComposerOutput(
        blocks=[
            {
                "id": "event-impact",
                "type": ReportBlockType.text,
                "title": "Impact",
                "content": "Collision occurs.",
                "sort_key": "0001",
                "provenance": ReportProvenance.evidence,
                "confidence_score": 0.8,
                "citations": [],
            },
        ]
    )

    normalized = normalize_composer_output(output, timeline)

    assert not validate_composer_output(normalized)
    assert normalized.blocks[0].citations[0].source_id == "ev-1"


def test_composer_output_normalization_sorts_blocks_by_sort_key():
    citation = Citation(
        source_id="ev-1",
        segment_id="seg-1",
        excerpt="Collision occurs in the intersection.",
        provenance=ReportProvenance.evidence,
    )
    timeline = TimelinePlan(
        timeline_events=[
            {
                "event_id": "impact",
                "title": "Impact",
                "narrative": "Collision occurs.",
                "sort_key": "0001",
                "evidence_refs": ["ev-1"],
                "citations": [citation.model_dump(mode="json")],
            }
        ]
    )
    output = ComposerOutput(
        blocks=[
            {
                "id": "event-impact",
                "type": ReportBlockType.text,
                "title": "Impact",
                "content": "Collision occurs.",
                "sort_key": "0001",
                "provenance": ReportProvenance.evidence,
                "confidence_score": 0.8,
                "citations": [citation.model_dump(mode="json")],
            },
            {
                "id": "event-approach",
                "type": ReportBlockType.text,
                "title": "Approach",
                "content": "Vehicles approach the intersection.",
                "sort_key": "0000",
                "provenance": ReportProvenance.evidence,
                "confidence_score": 0.9,
                "citations": [citation.model_dump(mode="json")],
            },
        ]
    )

    normalized = normalize_composer_output(output, timeline)

    assert not validate_composer_output(normalized)
    assert [block.id for block in normalized.blocks] == [
        "event-approach",
        "event-impact",
    ]


def test_media_plan_normalizes_request_block_types():
    media_plan = MediaPlan(
        image_requests=[
            {
                "block_id": "event-impact-image",
                "block_type": ReportBlockType.text,
                "anchor_block_id": "event-impact",
                "title": "Impact Still",
                "sort_key": "0001.10",
            }
        ],
        reconstruction_requests=[
            {
                "block_id": "event-impact-video",
                "block_type": ReportBlockType.text,
                "anchor_block_id": "event-impact",
                "title": "Impact Reconstruction",
                "sort_key": "0001.20",
            }
        ],
    )

    assert media_plan.image_requests[0].block_type == ReportBlockType.image
    assert media_plan.reconstruction_requests[0].block_type == ReportBlockType.video


def test_pipeline_result_normalizes_request_block_types():
    result = PipelineResult(
        blocks=[],
        image_requests=[
            {
                "block_id": "event-impact-image",
                "block_type": ReportBlockType.text,
                "anchor_block_id": "event-impact",
                "title": "Impact Still",
                "sort_key": "0001.10",
            }
        ],
        reconstruction_requests=[
            {
                "block_id": "event-impact-video",
                "block_type": ReportBlockType.text,
                "anchor_block_id": "event-impact",
                "title": "Impact Reconstruction",
                "sort_key": "0001.20",
            }
        ],
    )

    assert result.image_requests[0].block_type == ReportBlockType.image
    assert result.reconstruction_requests[0].block_type == ReportBlockType.video


def test_report_document_and_request_models_validate():
    bundle = CaseEvidenceBundle(
        case_id="case-1",
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                kind=EvidenceItemType.transcript,
                summary="Witness saw the vehicle stop.",
            )
        ],
    )
    request = GenerateReportRequest(bundle=bundle, max_images=2, max_reconstructions=1)
    assert request.max_images == 2
    assert request.bundle.case_id == "case-1"

    block = ReportBlock(
        id="block-1",
        type=ReportBlockType.text,
        title="Witness Statement",
        content="The witness reported the vehicle stopping before impact.",
        sort_key="0001",
        provenance=ReportProvenance.evidence,
        confidence_score=0.8,
        citations=[Citation(source_id="ev-1", provenance=ReportProvenance.evidence)],
        state=ReportBlockState.ready,
    )
    report = ReportDocument(
        report_id="report-1",
        status=ReportStatus.completed,
        sections=[block],
        warnings=[],
    )
    assert report.sections[0].citations[0].source_id == "ev-1"


def test_report_block_rejects_removed_timeline_type():
    with pytest.raises(ValidationError):
        ReportBlock(
            id="block-1",
            type="timeline",
            title="Legacy Timeline",
            content="Removed block type.",
            sort_key="0001",
            provenance=ReportProvenance.evidence,
            confidence_score=0.8,
            citations=[],
            state=ReportBlockState.ready,
        )
