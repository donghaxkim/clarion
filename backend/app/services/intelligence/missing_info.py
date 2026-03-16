from __future__ import annotations

from app.models.schema import CaseFile, EvidenceType, MissingInfo
from app.services.intelligence.citations import CitationIndex


def find_gaps(case: CaseFile, index: CitationIndex | None = None) -> list[MissingInfo]:
    evidence_types = {
        str(getattr(item.evidence_type, "value", item.evidence_type))
        for item in case.evidence
    }
    labels = {
        label.strip().lower()
        for item in case.evidence
        for label in item.labels
        if label and label.strip()
    }

    gaps: list[MissingInfo] = []
    is_vehicle_case = _looks_like_vehicle_case(case, labels)

    if _has_injury_signal(case, labels) and EvidenceType.MEDICAL_RECORD.value not in evidence_types:
        gaps.append(
            MissingInfo(
                severity="critical",
                description="No medical records are attached to support the claimed injury narrative.",
                recommendation=(
                    "Upload emergency room records, treatment notes, or imaging so injury causation "
                    "can be grounded in objective evidence."
                ),
            )
        )

    if is_vehicle_case and not evidence_types.intersection(
        {EvidenceType.DASHCAM_VIDEO.value, EvidenceType.SURVEILLANCE_VIDEO.value}
    ):
        gaps.append(
            MissingInfo(
                severity="warning",
                description="No video evidence is attached for the collision sequence.",
                recommendation=(
                    "Request dashcam, surveillance, or traffic camera footage to independently verify "
                    "speed, signal state, and the point of impact."
                ),
            )
        )

    if is_vehicle_case and EvidenceType.PHOTO.value not in evidence_types:
        gaps.append(
            MissingInfo(
                severity="suggestion",
                description="There are no scene or damage photographs in the workspace.",
                recommendation=(
                    "Add vehicle damage or scene photos to support reconstruction and severity analysis."
                ),
            )
        )

    if case.contradictions and not _has_official_record(evidence_types):
        gaps.append(
            MissingInfo(
                severity="warning",
                description="Key contradictions are present without an official record to anchor the timeline.",
                recommendation=(
                    "Upload police, insurance, employer, or other official records that can resolve "
                    "conflicting witness or party accounts."
                ),
            )
        )

    if index is not None:
        thin_dimensions = []
        for dimension in index.get_all_dimensions():
            source_ids = {
                fact.source_location.evidence_id
                for fact in index.query_by_dimension(dimension)
            }
            if len(source_ids) <= 1:
                thin_dimensions.append(dimension)
        if thin_dimensions:
            dimension_list = ", ".join(thin_dimensions[:3])
            gaps.append(
                MissingInfo(
                    severity="suggestion",
                    description=(
                        "Some important factual dimensions are supported by only one source: "
                        f"{dimension_list}."
                    ),
                    recommendation=(
                        "Add corroborating evidence for the weakest dimensions before relying on them "
                        "in the final liability narrative."
                    ),
                )
            )

    deduped: list[MissingInfo] = []
    seen = set()
    for gap in gaps:
        key = (gap.description, gap.recommendation)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gap)
    return deduped


def _looks_like_vehicle_case(case: CaseFile, labels: set[str]) -> bool:
    case_type = (case.case_type or "").lower()
    if "vehicle" in case_type or "collision" in case_type or "accident" in case_type:
        return True
    return any(
        token in labels
        for token in {
            "traffic_accident",
            "rear_end_collision",
            "collision",
            "intersection",
            "vehicle_damage",
        }
    )


def _has_injury_signal(case: CaseFile, labels: set[str]) -> bool:
    case_type = (case.case_type or "").lower()
    if "injury" in case_type or "medical" in case_type:
        return True
    if "injury" in labels or "pain" in labels:
        return True
    return any(entity.type == "injury" for entity in case.entities)


def _has_official_record(evidence_types: set[str]) -> bool:
    return bool(
        evidence_types.intersection(
            {
                EvidenceType.POLICE_REPORT.value,
                EvidenceType.INSURANCE_DOCUMENT.value,
                EvidenceType.MEDICAL_RECORD.value,
            }
        )
    )
