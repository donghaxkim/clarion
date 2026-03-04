"""
CLARION — Evidence Contradiction Detector
============================================
Finds conflicting facts across different evidence sources.

Key insight: Two facts can ONLY contradict if they're about the
SAME DIMENSION and the SAME ENTITY. This is true regardless of
case type — whether it's a car accident, medical malpractice,
contract dispute, or criminal case.

Dimensions are discovered dynamically by the citation index,
so this detector works for any case type without modification.

Three-stage pipeline:
  1. Pull fact groups from CitationIndex where multiple sources
     discuss the same (dimension, entity) pair
  2. Send only those candidates to Gemini for semantic conflict check
  3. Build Contradiction schema objects sorted by severity

Depends on: CitationIndex from citations.py
"""

import json
from app.models.schema import (
    CaseFile, Contradiction, ContradictionSeverity,
    SourceLocation, new_id,
)
from app.services.intelligence.citations import CitationIndex, IndexedFact
from app.utils.gemini_client import ask_gemini_json


# ──────────────────────────────────────────────
#  STEP 1 — FIND CANDIDATE PAIRS
# ──────────────────────────────────────────────

def find_candidate_pairs(
    index: CitationIndex,
) -> list[tuple[list[IndexedFact], str, str]]:
    """
    Identify groups of facts that COULD contradict — same dimension,
    same entity, but from DIFFERENT sources.

    Works for any case type because dimensions come from the index.
    """
    groups = index.get_facts_by_dimension_and_entity()
    candidates = []

    for dimension, entity_groups in groups.items():
        for entity_key, facts in entity_groups.items():
            # Only interesting if multiple sources discuss the same thing
            source_ids = set(f.source_location.evidence_id for f in facts)
            if len(source_ids) < 2:
                continue

            candidates.append((facts, dimension, entity_key))

    return candidates


# ──────────────────────────────────────────────
#  STEP 2 — SEMANTIC CONTRADICTION CHECK
# ──────────────────────────────────────────────

CONTRADICTION_PROMPT = """You are a legal contradiction analyzer. Determine if facts from different evidence sources contradict each other.

CASE TYPE: {case_type}
DIMENSION: {dimension}
ENTITY: {entity}

FACTS FROM DIFFERENT SOURCES:
{facts_json}

Analyze these facts and return a JSON object:

{{
    "contradictions": [
        {{
            "fact_a_index": 0,
            "fact_b_index": 1,
            "is_contradiction": true,
            "severity": "low" | "medium" | "high",
            "explanation": "Clear explanation of the conflict and why it matters for this case",
            "type": "direct_conflict" | "numerical_discrepancy" | "temporal_inconsistency" | "factual_disagreement" | "omission_conflict" | "attribution_conflict"
        }}
    ]
}}

CONTRADICTION TYPES (applicable to any case):
- direct_conflict: Two sources make incompatible claims about the same thing
- numerical_discrepancy: Different numbers, amounts, measurements, or quantities
- temporal_inconsistency: Different times, dates, or sequences of events
- factual_disagreement: Different accounts of what happened or what is true
- omission_conflict: One source claims something happened that another source's account implicitly denies
- attribution_conflict: Sources disagree about WHO did or said something

RULES — These apply regardless of case type:
- Two facts ONLY contradict if they make INCOMPATIBLE claims about the same thing
- Different wording for the same meaning is NOT a contradiction
- Vague vs specific is NOT a contradiction — it's just different precision
- One source adding detail the other omits is NOT a contradiction unless the omission implies something different
- Additional context or elaboration is NOT a contradiction

SEVERITY GUIDE:
- low: minor discrepancy that could be explained by perception, memory, or imprecision
- medium: notable conflict that affects understanding of the case
- high: critical conflict that could determine liability, credibility, or outcome

Only return actual contradictions. Empty array if none found. Do NOT over-flag.
"""


def check_contradictions_in_group(
    facts: list[IndexedFact],
    dimension: str,
    entity: str,
    case_type: str = "unknown",
) -> list[dict]:
    """
    Send a group of facts (same dimension + entity, different sources)
    to Gemini for semantic contradiction analysis.
    """
    facts_for_prompt = []
    for i, fact in enumerate(facts):
        facts_for_prompt.append({
            "index": i,
            "claim": fact.fact_text,
            "source_id": fact.source_location.evidence_id,
            "source_type": fact.evidence_type.value if hasattr(fact.evidence_type, 'value') else str(fact.evidence_type),
            "excerpt": fact.excerpt,
            "page": fact.source_location.page,
            "timestamp": fact.source_location.timestamp_start,
        })

    prompt = CONTRADICTION_PROMPT.format(
        case_type=case_type,
        dimension=dimension,
        entity=entity,
        facts_json=json.dumps(facts_for_prompt, indent=2),
    )

    result = ask_gemini_json(
        prompt=prompt,
        temperature=0.05,
    )

    contradictions = result.get("contradictions", [])

    enriched = []
    for c in contradictions:
        if not c.get("is_contradiction", False):
            continue

        idx_a = c.get("fact_a_index", 0)
        idx_b = c.get("fact_b_index", 1)

        if idx_a < len(facts) and idx_b < len(facts):
            enriched.append({
                **c,
                "fact_a": facts[idx_a],
                "fact_b": facts[idx_b],
                "dimension": dimension,
                "entity": entity,
            })

    return enriched


# ──────────────────────────────────────────────
#  STEP 3 — BUILD SCHEMA OBJECTS
# ──────────────────────────────────────────────

SEVERITY_MAP = {
    "low": ContradictionSeverity.LOW,
    "medium": ContradictionSeverity.MEDIUM,
    "high": ContradictionSeverity.HIGH,
}


def build_contradiction(raw: dict) -> Contradiction:
    """Convert a raw contradiction result into a schema Contradiction."""
    fact_a: IndexedFact = raw["fact_a"]
    fact_b: IndexedFact = raw["fact_b"]

    severity_str = raw.get("severity", "medium")
    severity = SEVERITY_MAP.get(severity_str, ContradictionSeverity.MEDIUM)

    conflict_type = raw.get("type", "direct_conflict").replace("_", " ")
    description = (
        f"[{conflict_type.upper()}] {raw.get('explanation', 'Conflicting claims detected')}"
    )

    return Contradiction(
        severity=severity,
        description=description,
        source_a=fact_a.source_location,
        source_b=fact_b.source_location,
        fact_a=fact_a.fact_text,
        fact_b=fact_b.fact_text,
        related_entities=list(set(fact_a.related_entities + fact_b.related_entities)),
    )


# ──────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────

def detect_contradictions(
    case: CaseFile,
    index: CitationIndex,
) -> list[Contradiction]:
    """
    Main entry point. Finds all contradictions across evidence.

    Works for ANY case type — dimensions and reliability come
    from the CitationIndex which discovers them dynamically.

    Call AFTER build_citation_index().
    """
    # Step 1: Find candidate groups
    candidate_groups = find_candidate_pairs(index)

    if not candidate_groups:
        return []

    all_contradictions = []

    # Step 2: Check each group for semantic contradictions
    for facts, dimension, entity in candidate_groups:
        if len(facts) < 2 or len(facts) > 20:
            continue

        raw_contradictions = check_contradictions_in_group(
            facts, dimension, entity,
            case_type=index.case_type,
        )

        # Step 3: Build schema objects
        for raw in raw_contradictions:
            contradiction = build_contradiction(raw)
            all_contradictions.append(contradiction)

    # Sort by severity (high first)
    severity_order = {
        ContradictionSeverity.HIGH: 0,
        ContradictionSeverity.MEDIUM: 1,
        ContradictionSeverity.LOW: 2,
    }
    all_contradictions.sort(key=lambda c: severity_order.get(c.severity, 1))

    return all_contradictions


def get_contradictions_for_entity(
    contradictions: list[Contradiction],
    entity_name: str,
) -> list[Contradiction]:
    """
    Filter contradictions relevant to a specific entity.
    Used by the witness selector feature.
    """
    entity_lower = entity_name.lower()
    return [
        c for c in contradictions
        if any(entity_lower in e.lower() for e in c.related_entities)
    ]


def get_contradictions_for_evidence(
    contradictions: list[Contradiction],
    evidence_id: str,
) -> list[Contradiction]:
    """
    Filter contradictions involving a specific piece of evidence.
    Used when displaying a single document view.
    """
    return [
        c for c in contradictions
        if c.source_a.evidence_id == evidence_id
        or c.source_b.evidence_id == evidence_id
    ]


def get_contradictions_for_dimension(
    contradictions: list[Contradiction],
    index: CitationIndex,
    dimension: str,
) -> list[Contradiction]:
    """
    Filter contradictions within a specific dimension.
    Useful for focused review — "show me all timeline conflicts."
    """
    # Get all evidence IDs with facts in this dimension
    dim_facts = index.query_by_dimension(dimension)
    dim_evidence_ids = set(f.source_location.evidence_id for f in dim_facts)

    return [
        c for c in contradictions
        if c.source_a.evidence_id in dim_evidence_ids
        and c.source_b.evidence_id in dim_evidence_ids
    ]


def summarize_contradictions(contradictions: list[Contradiction]) -> dict:
    """
    Quick summary stats for the UI dashboard.
    """
    return {
        "total": len(contradictions),
        "high": sum(1 for c in contradictions if c.severity == ContradictionSeverity.HIGH),
        "medium": sum(1 for c in contradictions if c.severity == ContradictionSeverity.MEDIUM),
        "low": sum(1 for c in contradictions if c.severity == ContradictionSeverity.LOW),
        "needs_attention": sum(
            1 for c in contradictions
            if c.severity in (ContradictionSeverity.HIGH, ContradictionSeverity.MEDIUM)
        ),
    }