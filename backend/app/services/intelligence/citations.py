"""
CLARION — Citation Services
==============================
Two citation systems coexist during migration:

1. ``link_citation`` — lightweight helper used by the reporting pipeline.
   Produces new-style Citation objects (report_schema).

2. ``CitationIndex`` / ``build_citation_index`` — full dimension-aware fact
   index used by the legacy intelligence layer (contradictions, entity
   analysis).  Uses old-schema models (schema.py).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

# ── New-style citation helper (reporting pipeline) ───────────────
from app.models import Citation as ReportCitation, ReportProvenance


def link_citation(claim: str, doc_id: str, page: int | None) -> dict:
    del claim
    return ReportCitation(
        source_id=doc_id,
        page_number=page,
        provenance=ReportProvenance.evidence,
    ).model_dump(mode="json")


# ── Full citation index (legacy intelligence layer) ─────────────
from app.models.schema import (
    CaseFile,
    Citation,
    EvidenceItem,
    EvidenceType,
    SourceLocation,
    new_id,
)
from app.utils.gemini_client import ask_gemini_json


# ──────────────────────────────────────────────
#  DYNAMIC DIMENSION DISCOVERY
# ──────────────────────────────────────────────

DISCOVER_DIMENSIONS_PROMPT = """You are a litigation analyst. Given summaries of evidence in a legal case, identify the KEY FACTUAL DIMENSIONS that matter for this case.

A dimension is a category of factual claims that different sources might agree or disagree on. For example:
- In a car accident case: speed, direction of travel, traffic signal state, right of way, point of impact
- In a medical malpractice case: standard of care, diagnosis accuracy, treatment timeline, informed consent, patient history
- In an employment dispute: termination reason, performance history, policy compliance, discriminatory intent, damages
- In a contract dispute: contract terms, performance obligations, breach specifics, notice requirements, damages calculation
- In a criminal case: suspect identification, timeline of events, weapon used, motive, alibi
- In a slip and fall: floor condition, warning signs present, maintenance schedule, footwear, lighting conditions
- In product liability: defect type, manufacturing process, warning labels, intended use, prior incidents
- In IP litigation: prior art, originality, access to work, substantial similarity, damages

EVIDENCE SUMMARIES:
{evidence_summaries}

CASE TYPE (if known): {case_type}

Return a JSON object:
{{
    "case_type_detected": "The type of case this appears to be",
    "dimensions": [
        {{
            "name": "short_snake_case_name",
            "description": "What facts fall into this dimension",
            "importance": "high" | "medium" | "low",
            "example_claims": ["Example of a fact in this dimension"]
        }}
    ],
    "source_reliability_ranking": [
        {{
            "evidence_type": "The type of evidence source",
            "reliability": 0.9,
            "reasoning": "Why this source type is this reliable for THIS specific case type"
        }}
    ]
}}

RULES:
- Return 8-20 dimensions tailored to THIS case
- Focus on dimensions where MULTIPLE sources might have competing claims
- Rank source reliability based on what matters for THIS case type
  (e.g. a contract is the most reliable source in a breach case,
   but medical records matter most in a malpractice case)
- Do NOT use generic one-size-fits-all dimensions
"""


def discover_dimensions(case: CaseFile) -> dict:
    """
    Analyze all evidence in a case and discover what dimensions matter.
    Run this ONCE after all evidence is parsed, before building the index.

    Returns:
        dict with 'dimensions', 'case_type_detected', and 'source_reliability_ranking'
    """
    summaries = []
    for ev in case.evidence:
        summary_text = ev.summary or "No summary available"
        labels = ", ".join(ev.labels) if ev.labels else "none"
        entity_names = ", ".join(e.name for e in ev.entities) if ev.entities else "none"

        summaries.append(
            f"- [{getattr(ev.evidence_type, 'value', ev.evidence_type)}] {ev.filename}: {summary_text} "
            f"(Labels: {labels} | Entities: {entity_names})"
        )

    prompt = DISCOVER_DIMENSIONS_PROMPT.format(
        evidence_summaries="\n".join(summaries),
        case_type=case.case_type or "Unknown — please detect from evidence",
    )

    result = ask_gemini_json(prompt=prompt, temperature=0.1)
    return result


# ──────────────────────────────────────────────
#  INDEXED FACT — Internal representation
# ──────────────────────────────────────────────

class IndexedFact:
    """
    A single fact extracted from evidence, enriched with
    dimension classification and source metadata.
    """
    def __init__(
        self,
        fact_id: str,
        fact_text: str,
        dimension: str,
        related_entities: list[str],
        source_location: SourceLocation,
        evidence_type: EvidenceType,
        category: str,
        excerpt: str,
        reliability: float,
    ):
        self.fact_id = fact_id
        self.fact_text = fact_text
        self.dimension = dimension
        self.related_entities = related_entities
        self.source_location = source_location
        self.evidence_type = evidence_type
        self.category = category
        self.excerpt = excerpt
        self.reliability = reliability


# ──────────────────────────────────────────────
#  STEP 1 — COLLECT FACTS FROM ALL EVIDENCE
# ──────────────────────────────────────────────

def collect_all_facts(case: CaseFile) -> list[dict]:
    """
    Gather key_facts from every parsed evidence item.
    Returns raw fact dicts with evidence metadata attached.
    """
    all_facts = []

    for evidence in case.evidence:
        facts = []
        if hasattr(evidence, '_analysis') and evidence._analysis:
            facts = evidence._analysis.get("key_facts", [])

        for fact in facts:
            all_facts.append({
                "fact": fact.get("fact", ""),
                "page": fact.get("page"),
                "timestamp_start": fact.get("timestamp_start"),
                "excerpt": fact.get("excerpt", ""),
                "category": fact.get("category", "other"),
                "speaker": fact.get("speaker"),
                "evidence_id": evidence.id,
                "evidence_type": evidence.evidence_type,
                "filename": evidence.filename,
            })

    return all_facts


# ──────────────────────────────────────────────
#  STEP 2 — CLASSIFY FACTS INTO DISCOVERED DIMENSIONS
# ──────────────────────────────────────────────

CLASSIFY_PROMPT = """You are classifying facts from legal evidence into case-specific dimensions.

THIS CASE'S DIMENSIONS:
{dimensions}

FACTS TO CLASSIFY:
{facts_json}

For each fact, return a JSON array where each element has:
{{
    "index": 0,
    "dimension": "the most relevant dimension name from the list above",
    "related_entities": ["names of people, vehicles, organizations, or objects this fact is about"],
    "normalized_claim": "restate the fact as a clear, concise, standalone claim"
}}

Rules:
- Each fact gets exactly ONE primary dimension
- Use dimension names EXACTLY as provided above
- If a fact doesn't fit any dimension, use "other"
- related_entities should use the most specific name available
- normalized_claim should be unambiguous and comparable to other claims about the same dimension
"""


def classify_facts(raw_facts: list[dict], dimensions: list[dict]) -> list[dict]:
    """
    Classify facts into the discovered dimensions for this case.
    """
    if not raw_facts:
        return []

    dim_descriptions = "\n".join(
        f"- {d['name']}: {d['description']}"
        for d in dimensions
    )

    BATCH_SIZE = 40
    all_classified = []

    for batch_start in range(0, len(raw_facts), BATCH_SIZE):
        batch = raw_facts[batch_start:batch_start + BATCH_SIZE]

        facts_for_prompt = [
            {"index": i, "fact": f["fact"], "source": f["filename"]}
            for i, f in enumerate(batch)
        ]

        prompt = CLASSIFY_PROMPT.format(
            dimensions=dim_descriptions,
            facts_json=json.dumps(facts_for_prompt, indent=2),
        )

        result = ask_gemini_json(prompt=prompt, temperature=0.05)

        if isinstance(result, list):
            classified_batch = result
        else:
            classified_batch = result.get("facts", result.get("classifications", []))

        for item in classified_batch:
            idx = item.get("index", 0)
            if idx < len(batch):
                original = batch[idx]
                all_classified.append({
                    **original,
                    "dimension": item.get("dimension", "other"),
                    "related_entities": item.get("related_entities", []),
                    "normalized_claim": item.get("normalized_claim", original["fact"]),
                })

    return all_classified


# ──────────────────────────────────────────────
#  THE CITATION INDEX
# ──────────────────────────────────────────────

class CitationIndex:
    """
    The master fact index for the entire case.

    Queryable by:
      - dimension ("give me everything about standard_of_care")
      - entity ("give me everything about Dr. Smith")
      - dimension + entity (most precise)

    Each query returns facts ranked by source reliability.
    Dimensions and reliability are case-specific, not hardcoded.
    """

    def __init__(self):
        self.facts: list[IndexedFact] = []
        self._by_dimension: dict[str, list[IndexedFact]] = {}
        self._by_entity: dict[str, list[IndexedFact]] = {}
        self.dimensions: list[dict] = []
        self.case_type: str = "unknown"
        self.reliability_map: dict[str, float] = {}

    def add_fact(self, fact: IndexedFact):
        self.facts.append(fact)

        if fact.dimension not in self._by_dimension:
            self._by_dimension[fact.dimension] = []
        self._by_dimension[fact.dimension].append(fact)

        for entity in fact.related_entities:
            key = entity.lower().strip()
            if key not in self._by_entity:
                self._by_entity[key] = []
            self._by_entity[key].append(fact)

    def query_by_dimension(self, dimension: str) -> list[IndexedFact]:
        """All facts in a dimension, ranked by reliability."""
        facts = self._by_dimension.get(dimension, [])
        return sorted(facts, key=lambda f: f.reliability, reverse=True)

    def query_by_entity(self, entity_name: str) -> list[IndexedFact]:
        """All facts about an entity, ranked by reliability."""
        key = entity_name.lower().strip()
        matches = []
        for stored_key, facts in self._by_entity.items():
            if key in stored_key or stored_key in key:
                matches.extend(facts)
        return sorted(matches, key=lambda f: f.reliability, reverse=True)

    def query(
        self,
        dimension: str | None = None,
        entity: str | None = None,
    ) -> list[IndexedFact]:
        """Query by dimension, entity, or both."""
        if dimension and entity:
            dim_facts = set(id(f) for f in self.query_by_dimension(dimension))
            entity_facts = self.query_by_entity(entity)
            results = [f for f in entity_facts if id(f) in dim_facts]
            return sorted(results, key=lambda f: f.reliability, reverse=True)
        elif dimension:
            return self.query_by_dimension(dimension)
        elif entity:
            return self.query_by_entity(entity)
        else:
            return sorted(self.facts, key=lambda f: f.reliability, reverse=True)

    def get_facts_by_dimension_and_entity(self) -> dict[str, dict[str, list[IndexedFact]]]:
        """
        Facts grouped by (dimension, entity) pairs.
        This is what the contradiction detector consumes.
        """
        groups: dict[str, dict[str, list[IndexedFact]]] = {}
        for fact in self.facts:
            if fact.dimension not in groups:
                groups[fact.dimension] = {}
            for entity in fact.related_entities:
                key = entity.lower().strip()
                if key not in groups[fact.dimension]:
                    groups[fact.dimension][key] = []
                groups[fact.dimension][key].append(fact)
        return groups

    def get_all_dimensions(self) -> list[str]:
        """List all dimensions that have at least one fact."""
        return list(self._by_dimension.keys())

    def get_all_entities(self) -> list[str]:
        """List all entities that have at least one fact."""
        return list(self._by_entity.keys())

    def to_citation(self, fact: IndexedFact) -> Citation:
        """Convert an IndexedFact to a schema Citation object."""
        source_pin = fact.source_location.to_source_pin()
        return Citation(
            source=source_pin,
            label=source_pin.detail,
        )


# ──────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────

DEFAULT_RELIABILITY = {
    EvidenceType.POLICE_REPORT: 0.85,
    EvidenceType.MEDICAL_RECORD: 0.85,
    EvidenceType.DASHCAM_VIDEO: 0.9,
    EvidenceType.SURVEILLANCE_VIDEO: 0.9,
    EvidenceType.INSURANCE_DOCUMENT: 0.7,
    EvidenceType.WITNESS_STATEMENT: 0.6,
    EvidenceType.PHOTO: 0.75,
    EvidenceType.DIAGRAM: 0.5,
    EvidenceType.OTHER: 0.4,
}


def build_citation_index(case: CaseFile) -> CitationIndex:
    """
    Main entry point. Takes a CaseFile with parsed evidence,
    discovers case-specific dimensions, classifies all facts,
    and returns a fully populated CitationIndex.

    Call AFTER all evidence is parsed, BEFORE report generation.
    """
    index = CitationIndex()

    # Step 0: Discover dimensions from actual evidence
    discovery = discover_dimensions(case)
    index.dimensions = discovery.get("dimensions", [])
    index.case_type = discovery.get("case_type_detected", "unknown")

    # Build reliability map from case-specific ranking
    reliability_ranking = discovery.get("source_reliability_ranking", [])
    for entry in reliability_ranking:
        ev_type_str = entry.get("evidence_type", "")
        try:
            ev_type = EvidenceType(ev_type_str)
            index.reliability_map[ev_type] = entry.get("reliability", 0.5)
        except ValueError:
            pass

    # Step 1: Collect all raw facts
    raw_facts = collect_all_facts(case)

    if not raw_facts:
        return index

    # Step 2: Classify into discovered dimensions
    classified = classify_facts(raw_facts, index.dimensions)

    # Step 3: Build the index
    for fact_data in classified:
        evidence_type = fact_data.get("evidence_type", EvidenceType.OTHER)
        if isinstance(evidence_type, str):
            try:
                evidence_type = EvidenceType(evidence_type)
            except ValueError:
                evidence_type = EvidenceType.OTHER

        reliability = index.reliability_map.get(
            evidence_type,
            DEFAULT_RELIABILITY.get(evidence_type, 0.4),
        )

        source_location = SourceLocation(
            evidence_id=fact_data["evidence_id"],
            page=fact_data.get("page"),
            timestamp_start=fact_data.get("timestamp_start"),
            excerpt=fact_data.get("excerpt", ""),
        )

        indexed = IndexedFact(
            fact_id=new_id(),
            fact_text=fact_data.get("normalized_claim", fact_data["fact"]),
            dimension=fact_data.get("dimension", "other"),
            related_entities=fact_data.get("related_entities", []),
            source_location=source_location,
            evidence_type=evidence_type,
            category=fact_data.get("category", "other"),
            excerpt=fact_data.get("excerpt", ""),
            reliability=reliability,
        )

        index.add_fact(indexed)

    return index


def cite_claim(
    claim: str,
    index: CitationIndex,
    dimension: str | None = None,
    entity: str | None = None,
    top_k: int = 3,
) -> list[Citation]:
    """
    Given a claim in the report, find the best citations.

    Works for ANY case type:
        # Car accident
        cite_claim("Defendant was going 45 mph", index, dimension="speed", entity="defendant")

        # Medical malpractice
        cite_claim("Dr. Smith failed to order an MRI", index, dimension="diagnosis_timeline", entity="Dr. Smith")

        # Contract dispute
        cite_claim("Payment was due by March 1st", index, dimension="payment_terms", entity="defendant corp")
    """
    facts = index.query(dimension=dimension, entity=entity)
    return [index.to_citation(f) for f in facts[:top_k]]
