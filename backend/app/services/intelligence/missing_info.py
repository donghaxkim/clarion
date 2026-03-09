"""
CLARION — Missing Info Detector
==================================
Identifies gaps in the evidence that could weaken the case.

Two-stage approach:
  1. STRUCTURAL GAPS — Based on what evidence types are present vs expected
     for this case type. Fast, no Gemini call needed.
     e.g. "Personal injury case has no medical records uploaded"

  2. SEMANTIC GAPS — Gemini analyzes the actual content and finds what's
     missing based on claims made in the evidence.
     e.g. "Witness mentions a traffic camera but no surveillance footage uploaded"
     e.g. "Medical report references MRI results but no imaging uploaded"
     e.g. "Police report mentions a second witness but no statement from them"

Uses the CitationIndex to understand what dimensions have thin coverage.
"""

import json
from app.models.schema import CaseFile, MissingInfo, _id
from app.services.intelligence.citations import CitationIndex
from app.utils.gemini_client import ask_gemini_json


# ──────────────────────────────────────────────
#  STAGE 1 — STRUCTURAL GAP DETECTION
# ──────────────────────────────────────────────

# What evidence types you'd typically expect for each case type.
# These are suggestions, not requirements — severity is "suggestion" or "warning".
EXPECTED_EVIDENCE = {
    "personal_injury": {
        "medical_record": {"severity": "critical", "recommendation": "Upload medical records documenting injuries, treatment, and prognosis"},
        "photo": {"severity": "warning", "recommendation": "Upload photos of injuries and/or property damage"},
        "police_report": {"severity": "warning", "recommendation": "Upload the police/incident report if one exists"},
    },
    "personal_injury_auto_accident": {
        "police_report": {"severity": "critical", "recommendation": "Upload the police accident report"},
        "medical_record": {"severity": "critical", "recommendation": "Upload all medical records related to injuries from this accident"},
        "photo": {"severity": "warning", "recommendation": "Upload photos of vehicle damage and any visible injuries"},
        "witness_statement": {"severity": "suggestion", "recommendation": "Upload witness statements if available"},
        "dashcam_video": {"severity": "suggestion", "recommendation": "Upload dashcam or surveillance footage if available"},
    },
    "medical_malpractice": {
        "medical_record": {"severity": "critical", "recommendation": "Upload all relevant medical records including pre-existing conditions"},
        "witness_statement": {"severity": "warning", "recommendation": "Upload expert medical opinions if available"},
    },
    "slip_and_fall": {
        "photo": {"severity": "critical", "recommendation": "Upload photos of the hazardous condition and the scene"},
        "medical_record": {"severity": "critical", "recommendation": "Upload medical records documenting injuries"},
        "witness_statement": {"severity": "warning", "recommendation": "Upload witness statements from anyone who saw the incident or the condition"},
    },
    "employment": {
        "other": {"severity": "warning", "recommendation": "Upload employment contracts, HR policies, and relevant communications"},
    },
    "contract_dispute": {
        "other": {"severity": "critical", "recommendation": "Upload the contract(s) in question"},
    },
}


def detect_structural_gaps(case: CaseFile, case_type: str) -> list[MissingInfo]:
    """
    Check which expected evidence types are missing for this case type.
    Fast — no Gemini call needed.
    """
    gaps = []

    # Get the expected evidence map, fall back to a generic one
    expected = EXPECTED_EVIDENCE.get(case_type, {})
    if not expected:
        # Try matching partial case type (e.g. "personal_injury_auto" matches "personal_injury")
        for key, val in EXPECTED_EVIDENCE.items():
            if key in case_type or case_type in key:
                expected = val
                break

    if not expected:
        return gaps

    # What evidence types do we actually have?
    present_types = set(ev.evidence_type for ev in case.evidence)

    for ev_type, config in expected.items():
        if ev_type not in present_types:
            gaps.append(MissingInfo(
                severity=config["severity"],
                description=f"No {ev_type.replace('_', ' ')} uploaded for this {case_type.replace('_', ' ')} case",
                recommendation=config["recommendation"],
            ))

    return gaps


# ──────────────────────────────────────────────
#  STAGE 2 — SEMANTIC GAP DETECTION
# ──────────────────────────────────────────────

SEMANTIC_GAP_PROMPT = """You are a litigation support analyst reviewing a case file for gaps and missing evidence.

CASE TYPE: {case_type}

EVIDENCE UPLOADED:
{evidence_list}

KEY FACTS EXTRACTED (by dimension):
{facts_by_dimension}

ENTITIES IN THE CASE:
{entities}

Analyze this case and identify MISSING evidence or information gaps that could weaken the case. Look for:

1. REFERENCED BUT NOT UPLOADED — Evidence mentioned in existing documents that hasn't been provided
   (e.g., "police report mentions a traffic camera" but no surveillance footage uploaded,
    "medical report references MRI results" but no imaging provided,
    "witness mentions another person saw the accident" but no statement from that person)

2. THIN DIMENSIONS — Case dimensions where you have claims but very little supporting evidence
   (e.g., only one source for a critical claim about speed or fault)

3. STANDARD GAPS — Evidence that would normally strengthen this type of case but is absent
   (e.g., expert testimony in a malpractice case, financial records in a damages claim)

4. TEMPORAL GAPS — Missing evidence from important time periods
   (e.g., no medical records between initial ER visit and follow-up 3 months later)

Return a JSON object:
{{
    "gaps": [
        {{
            "severity": "suggestion" | "warning" | "critical",
            "description": "Clear description of what's missing",
            "recommendation": "Specific action to take to fill this gap",
            "reason": "Why this matters for the case"
        }}
    ]
}}

SEVERITY GUIDE:
- critical: Missing evidence that could seriously undermine the case or a key claim
- warning: Notable gap that opposing counsel could exploit
- suggestion: Would strengthen the case but not essential

Be specific and actionable. Do NOT flag things that are genuinely optional.
Return 3-10 gaps, prioritized by severity.
"""


def detect_semantic_gaps(case: CaseFile, index: CitationIndex) -> list[MissingInfo]:
    """
    Use Gemini to analyze actual evidence content and find semantic gaps.
    """
    # Build evidence list for prompt
    evidence_list = "\n".join(
        f"- [{ev.evidence_type}] {ev.filename}: {ev.summary or 'No summary'}"
        for ev in case.evidence
    )

    # Build facts by dimension
    dims = index.get_all_dimensions()
    facts_by_dim_lines = []
    for dim in dims:
        facts = index.query_by_dimension(dim)
        fact_texts = [f"  - {f.fact_text} (from {f.filename})" for f in facts[:5]]
        source_count = len(set(f.evidence_id for f in facts))
        facts_by_dim_lines.append(
            f"{dim} ({len(facts)} facts from {source_count} sources):\n" + "\n".join(fact_texts)
        )
    facts_by_dimension = "\n\n".join(facts_by_dim_lines) if facts_by_dim_lines else "No facts indexed yet"

    # Build entity list
    entities = "\n".join(
        f"- [{e.type}] {e.name}" + (f" (aliases: {', '.join(e.aliases)})" if e.aliases else "")
        for e in case.entities
    )

    prompt = SEMANTIC_GAP_PROMPT.format(
        case_type=index.case_type or case.case_type or "unknown",
        evidence_list=evidence_list,
        facts_by_dimension=facts_by_dimension,
        entities=entities or "No entities extracted",
    )

    result = ask_gemini_json(prompt=prompt, temperature=0.2)

    gaps = []
    for g in result.get("gaps", []):
        gaps.append(MissingInfo(
            severity=g.get("severity", "suggestion"),
            description=g["description"],
            recommendation=g.get("recommendation"),
        ))

    return gaps


# ──────────────────────────────────────────────
#  STAGE 3 — THIN DIMENSION DETECTION
# ──────────────────────────────────────────────

def detect_thin_dimensions(index: CitationIndex) -> list[MissingInfo]:
    """
    Find dimensions where critical claims have only one source.
    A claim backed by a single source is vulnerable to attack.
    No Gemini call needed — pure logic on the citation index.
    """
    gaps = []

    # Check high-importance dimensions
    high_importance_dims = [
        d["name"] for d in index.dimensions
        if d.get("importance") == "high"
    ]

    for dim in high_importance_dims:
        facts = index.query_by_dimension(dim)
        if not facts:
            continue

        source_ids = set(f.evidence_id for f in facts)
        if len(source_ids) == 1:
            source_file = facts[0].filename
            gaps.append(MissingInfo(
                severity="warning",
                description=f"The '{dim.replace('_', ' ')}' dimension has evidence from only one source ({source_file}). A single-source claim on a critical dimension is vulnerable to challenge.",
                recommendation=f"Find additional evidence that corroborates claims about {dim.replace('_', ' ')}. Consider witness statements, video footage, or expert analysis.",
            ))

    return gaps


# ──────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────

def detect_missing_info(case: CaseFile, index: CitationIndex) -> list[MissingInfo]:
    """
    Main entry point. Runs all three detection stages and returns
    combined, deduplicated results sorted by severity.

    Call AFTER build_citation_index().
    """
    all_gaps = []

    # Stage 1: Structural gaps (fast, no API call)
    case_type = index.case_type or case.case_type or "unknown"
    structural = detect_structural_gaps(case, case_type)
    all_gaps.extend(structural)

    # Stage 2: Semantic gaps (Gemini call)
    try:
        semantic = detect_semantic_gaps(case, index)
        all_gaps.extend(semantic)
    except Exception:
        # Don't let semantic detection failure break the pipeline
        pass

    # Stage 3: Thin dimension detection (fast, no API call)
    thin = detect_thin_dimensions(index)
    all_gaps.extend(thin)

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "suggestion": 2}
    all_gaps.sort(key=lambda g: severity_order.get(g.severity, 2))

    return all_gaps