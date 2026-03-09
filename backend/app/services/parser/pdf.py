"""
CLARION — PDF Parser Service
==============================
YOUR primary service. Takes a raw PDF file and outputs a fully
structured EvidenceItem with extracted text, entities, labels, and summary.

Flow:
  1. Extract raw text + tables with pdfplumber
  2. Send extracted text to Gemini for structured understanding
  3. Assemble into EvidenceItem matching schema.py

Handles: police reports, medical records, insurance docs, and generic PDFs.
"""

import pdfplumber
import json
from pathlib import Path
from datetime import datetime

from app.models.schema import (
    EvidenceItem, EvidenceType, ExtractedContent, MediaRef,
    Entity, SourceLocation, new_id,
)
from app.utils.gemini_client import ask_gemini_json


# ──────────────────────────────────────────────
#  STEP 1 — RAW EXTRACTION
# ──────────────────────────────────────────────

def extract_text_and_tables(pdf_path: str) -> dict:
    """
    Extract raw text and tables from every page of a PDF.
    Returns structured output with per-page content.
    """
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_data = {
                "page_number": i + 1,
                "text": page.extract_text() or "",
                "tables": [],
            }

            # Extract tables as list of lists
            raw_tables = page.extract_tables()
            if raw_tables:
                for table in raw_tables:
                    if table and len(table) > 1:
                        # Convert to list of dicts using first row as headers
                        headers = [h or f"col_{j}" for j, h in enumerate(table[0])]
                        rows = []
                        for row in table[1:]:
                            row_dict = {}
                            for j, cell in enumerate(row):
                                key = headers[j] if j < len(headers) else f"col_{j}"
                                row_dict[key] = cell or ""
                            rows.append(row_dict)
                        page_data["tables"].append(rows)

            pages.append(page_data)

    # Combine all text for full-document analysis
    full_text = "\n\n".join(
        f"[Page {p['page_number']}]\n{p['text']}" for p in pages
    )

    all_tables = []
    for p in pages:
        all_tables.extend(p["tables"])

    return {
        "pages": pages,
        "full_text": full_text,
        "tables": all_tables,
        "page_count": len(pages),
    }


# ──────────────────────────────────────────────
#  STEP 2 — GEMINI STRUCTURED ANALYSIS
# ──────────────────────────────────────────────

ANALYSIS_PROMPT = """You are a legal document analyzer for a litigation support tool called Clarion.

Analyze the following document text extracted from a PDF and return structured JSON.

IMPORTANT — document_type: Use ONLY these when the document is clearly that type of legal evidence:
- police_report: official police/incident/accident report
- medical_record: medical chart, doctor notes, hospital records
- insurance_document: insurance policy, claim, or coverage doc
- witness_statement: written statement from a witness about an incident
- diagram: accident diagram, scene sketch, or technical drawing

Use "other" for anything that is NOT legal evidence: resumes, CVs, cover letters, brochures, flyers, forms that are not incident-related, or any document that does not clearly fit the types above. When in doubt, use "other".

DOCUMENT TEXT:
---
{document_text}
---

Return a JSON object with these exact fields:

{{
    "document_type": "police_report" | "medical_record" | "insurance_document" | "witness_statement" | "diagram" | "other",

    "summary": "A concise 2-3 sentence summary of this document. If it is legal evidence, focus on key facts relevant to a case; if it is 'other' (e.g. resume), summarize what the document is.",

    "labels": ["list", "of", "relevant", "tags"],
    // Examples: "traffic_accident", "rear_end_collision", "intersection", "speeding",
    // "lumbar_injury", "surgery_required", "liability_disputed", etc.

    "entities": [
        {{
            "type": "person" | "vehicle" | "location" | "date" | "injury" | "organization",
            "name": "Display name (e.g., 'Officer James Miller', '2019 Red Honda Civic', 'Main St & 5th Ave')",
            "aliases": ["other names used in the document for this same entity"],
            "mentions": [
                {{
                    "page": 1,
                    "excerpt": "Short verbatim quote where this entity is mentioned"
                }}
            ]
        }}
    ],

    "key_facts": [
        {{
            "fact": "A single factual claim from the document",
            "page": 1,
            "excerpt": "The verbatim text supporting this fact",
            "category": "incident_description" | "injury" | "timeline" | "liability" | "witness_account" | "medical_finding" | "financial" | "other"
        }}
    ],

    "timeline_events": [
        {{
            "timestamp": "Display format (e.g., '2:34 PM, March 5, 2024')",
            "description": "What happened at this time",
            "page": 1
        }}
    ]
}}

Extract EVERY entity, fact, and timeline event you can find. Be thorough.
For the summary, focus on facts that matter for litigation — liability, damages, causation.
"""


def analyze_with_gemini(full_text: str, page_count: int) -> dict:
    """
    Send extracted text to Gemini for structured understanding.
    Returns parsed JSON with document type, entities, facts, timeline.
    """
    # Truncate if extremely long (Gemini context is large but be safe)
    truncated = full_text[:50000] if len(full_text) > 50000 else full_text

    prompt = ANALYSIS_PROMPT.format(document_text=truncated)

    result = ask_gemini_json(
        prompt=prompt,
        system_instruction=(
            "You are a precise legal document analyzer. "
            "Extract facts exactly as stated in the document. "
            "Never infer or fabricate information. "
            "If something is unclear, note it as such."
        ),
        temperature=0.1,
    )

    return result


# ──────────────────────────────────────────────
#  STEP 3 — ASSEMBLE INTO SCHEMA
# ──────────────────────────────────────────────

# Map Gemini's document_type to our EvidenceType enum
DOC_TYPE_MAP = {
    "police_report": EvidenceType.POLICE_REPORT,
    "medical_record": EvidenceType.MEDICAL_RECORD,
    "insurance_document": EvidenceType.INSURANCE_DOCUMENT,
    "witness_statement": EvidenceType.WITNESS_STATEMENT,
    "diagram": EvidenceType.DIAGRAM,
    "other": EvidenceType.OTHER,
}


def build_evidence_item(
    filename: str,
    media_url: str,
    extraction: dict,
    analysis: dict,
) -> EvidenceItem:
    """
    Combine raw extraction + Gemini analysis into a schema-compliant EvidenceItem.
    """
    evidence_id = new_id()

    # Build entities with source locations
    entities = []
    for ent_data in analysis.get("entities", []):
        entity = Entity(
            type=ent_data["type"],
            name=ent_data["name"],
            aliases=ent_data.get("aliases", []),
            mentions=[
                SourceLocation(
                    evidence_id=evidence_id,
                    page=m.get("page"),
                    excerpt=m.get("excerpt"),
                )
                for m in ent_data.get("mentions", [])
            ],
        )
        entities.append(entity)

    # Build extracted content
    content = ExtractedContent(
        text=extraction["full_text"],
        tables=extraction["tables"] if extraction["tables"] else None,
    )

    # Map document type
    doc_type_str = analysis.get("document_type", "other")
    evidence_type = DOC_TYPE_MAP.get(doc_type_str, EvidenceType.OTHER)

    # Build the evidence item
    evidence = EvidenceItem(
        id=evidence_id,
        filename=filename,
        evidence_type=evidence_type,
        media=MediaRef(
            url=media_url,
            media_type="application/pdf",
        ),
        content=content,
        entities=entities,
        labels=analysis.get("labels", []),
        summary=analysis.get("summary"),
    )

    # Attach key_facts and timeline_events as metadata
    # These get stored alongside the evidence for the intelligence layer
    evidence._analysis = analysis  # temporarily stash for downstream use

    return evidence


# ──────────────────────────────────────────────
#  PUBLIC API — What the router calls
# ──────────────────────────────────────────────

def parse_pdf(
    pdf_path: str,
    filename: str,
    media_url: str,
) -> EvidenceItem:
    """
    Main entry point. Takes a PDF file path, returns a structured EvidenceItem.

    Args:
        pdf_path:  Local path to the uploaded PDF file
        filename:  Original filename from the user
        media_url: GCS URL where the original PDF is stored

    Returns:
        EvidenceItem ready to be added to the CaseFile
    """
    # Step 1: Raw extraction
    extraction = extract_text_and_tables(pdf_path)

    # Step 2: Gemini analysis
    analysis = analyze_with_gemini(
        full_text=extraction["full_text"],
        page_count=extraction["page_count"],
    )

    # Step 3: Assemble
    evidence = build_evidence_item(
        filename=filename,
        media_url=media_url,
        extraction=extraction,
        analysis=analysis,
    )

    return evidence


def get_key_facts(evidence: EvidenceItem) -> list[dict]:
    """
    Retrieve the key facts extracted by Gemini.
    Used downstream by the contradiction detector and citation tracker.
    """
    if hasattr(evidence, '_analysis') and evidence._analysis:
        return evidence._analysis.get("key_facts", [])
    return []


def get_timeline_events(evidence: EvidenceItem) -> list[dict]:
    """
    Retrieve timeline events extracted by Gemini.
    Used downstream by the report generator for the timeline block.
    """
    if hasattr(evidence, '_analysis') and evidence._analysis:
        return evidence._analysis.get("timeline_events", [])
    return []