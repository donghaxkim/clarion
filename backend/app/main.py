"""
CLARION — FastAPI Application
===============================
Main entry point. Defines all API routes.

Endpoints:
  POST /api/upload          → Upload evidence files, get parsed + analyzed CaseFile
  POST /api/generate        → Trigger report generation (Larris's domain)
  GET  /api/stream/{id}     → SSE stream of report sections as they generate
  POST /api/edit-section    → Edit a specific report section via side panel chat
  GET  /api/export/{id}     → Export report to courtroom-presentable format
  GET  /api/case/{id}       → Get current state of a case
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import os
import tempfile
import shutil
from datetime import datetime

from app.models.schema import (
    CaseFile, EvidenceItem, EvidenceType, MediaRef, new_id,
)
from app.services.parser.labeler import parse_evidence, detect_file_type
from app.services.intelligence.citations import build_citation_index, CitationIndex
from app.services.intelligence.contradictions import (
    detect_contradictions, summarize_contradictions,
)

# ──────────────────────────────────────────────
#  APP SETUP
# ──────────────────────────────────────────────

app = FastAPI(
    title="Clarion API",
    description="AI-powered litigation visual engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory case storage (swap for a database in production)
# For hackathon, this is fine — everything lives in memory
cases: dict[str, CaseFile] = {}
citation_indices: dict[str, CitationIndex] = {}


# ──────────────────────────────────────────────
#  STORAGE HELPERS
# ──────────────────────────────────────────────

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/clarion-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_upload(file: UploadFile) -> tuple[str, str]:
    """
    Save uploaded file to local disk (or GCS in production).
    Returns (local_path, media_url).
    """
    file_id = new_id()
    filename = file.filename or f"upload_{file_id}"
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")

    with open(local_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # In production, upload to GCS and return signed URL
    # For hackathon, use local file path as the "URL"
    media_url = f"file://{local_path}"

    return local_path, media_url


# ──────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────

@app.post("/api/case/create")
async def create_case(
    title: Optional[str] = Form(None),
    case_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """
    Create a new empty case. Returns case ID.
    Call this first, then upload evidence to it.
    """
    case = CaseFile(
        title=title,
        case_type=case_type,
        description=description,
        status="intake",
    )
    cases[case.id] = case

    return {
        "case_id": case.id,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
    }


@app.post("/api/case/{case_id}/upload")
async def upload_evidence(
    case_id: str,
    files: list[UploadFile] = File(...),
):
    """
    Upload one or more evidence files to a case.
    Each file is parsed, labeled, and added to the case.
    Video files are flagged for Larris's pipeline.

    Returns parsed evidence items with auto-labels and entities.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    case.status = "parsing"
    case.updated_at = datetime.utcnow()

    results = []
    video_files = []

    for file in files:
        # Save the file
        local_path, media_url = await save_upload(file)
        filename = file.filename or "unknown"
        file_type = detect_file_type(filename)

        if file_type == "video":
            # Video goes to Larris's pipeline
            video_files.append({
                "filename": filename,
                "local_path": local_path,
                "media_url": media_url,
                "file_type": "video",
                "status": "pending_video_analysis",
            })
            continue

        # Parse with your pipeline
        try:
            evidence = parse_evidence(local_path, filename, media_url)

            if evidence:
                case.evidence.append(evidence)

                # Merge entities into the case-level entity list
                for entity in evidence.entities:
                    # Check if entity already exists (by name match)
                    existing = next(
                        (e for e in case.entities if e.name.lower() == entity.name.lower()),
                        None,
                    )
                    if existing:
                        # Merge mentions into existing entity
                        existing.mentions.extend(entity.mentions)
                        existing.aliases = list(set(existing.aliases + entity.aliases))
                    else:
                        case.entities.append(entity)

                results.append({
                    "evidence_id": evidence.id,
                    "filename": evidence.filename,
                    "evidence_type": getattr(evidence.evidence_type, "value", evidence.evidence_type),
                    "labels": evidence.labels,
                    "summary": evidence.summary,
                    "entity_count": len(evidence.entities),
                    "entities": [
                        {"type": e.type, "name": e.name}
                        for e in evidence.entities
                    ],
                    "status": "parsed",
                })
            else:
                results.append({
                    "filename": filename,
                    "status": "parse_failed",
                    "error": "Could not parse file",
                })

        except Exception as e:
            results.append({
                "filename": filename,
                "status": "parse_failed",
                "error": str(e),
            })

    case.status = "intake"
    case.updated_at = datetime.utcnow()
    cases[case_id] = case

    return {
        "case_id": case_id,
        "parsed": results,
        "video_pending": video_files,
        "total_evidence": len(case.evidence),
        "total_entities": len(case.entities),
    }


@app.post("/api/case/{case_id}/analyze")
async def analyze_case(case_id: str):
    """
    Run the intelligence layer on all parsed evidence.
    Builds citation index and detects contradictions.

    Call this AFTER all evidence is uploaded, BEFORE generating report.
    Returns contradictions and case analysis.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]

    if len(case.evidence) == 0:
        raise HTTPException(status_code=400, detail="No evidence uploaded yet")

    case.status = "analyzing"
    case.updated_at = datetime.utcnow()

    # Build citation index (discovers dimensions + classifies facts)
    index = build_citation_index(case)
    citation_indices[case_id] = index

    # Detect contradictions
    contradictions = detect_contradictions(case, index)
    case.contradictions = contradictions

    case.status = "analyzed"
    case.updated_at = datetime.utcnow()
    cases[case_id] = case

    return {
        "case_id": case_id,
        "case_type_detected": index.case_type,
        "dimensions_discovered": [
            {"name": d["name"], "description": d["description"], "importance": d["importance"]}
            for d in index.dimensions
        ],
        "total_facts_indexed": len(index.facts),
        "total_entities": len(case.entities),
        "entities": [
            {"type": e.type, "name": e.name, "mention_count": len(e.mentions)}
            for e in case.entities
        ],
        "contradictions": {
            "summary": summarize_contradictions(contradictions),
            "items": [
                {
                    "id": c.id,
                    "severity": getattr(c.severity, "value", c.severity),
                    "description": c.description,
                    "fact_a": c.fact_a,
                    "fact_b": c.fact_b,
                    "related_entities": c.related_entities,
                }
                for c in contradictions
            ],
        },
    }


@app.post("/api/case/{case_id}/generate")
async def generate_report(case_id: str):
    """
    Trigger report generation.
    This calls Larris's generation engine.

    Placeholder — Larris implements the actual generation logic.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    index = citation_indices.get(case_id)

    if not index:
        raise HTTPException(
            status_code=400,
            detail="Case not analyzed yet. Call /analyze first.",
        )

    case.status = "generating"
    case.updated_at = datetime.utcnow()

    # ─── LARRIS IMPLEMENTS THIS ───
    # from app.services.generation.report import generate_report_sections
    # sections = generate_report_sections(case, index)
    # case.report_sections = sections
    # ──────────────────────────────

    return {
        "case_id": case_id,
        "status": "generating",
        "message": "Report generation started. Connect to SSE stream for real-time updates.",
        "stream_url": f"/api/stream/{case_id}",
    }


@app.get("/api/stream/{case_id}")
async def stream_report(case_id: str):
    """
    SSE endpoint for streaming report sections as they generate.
    Person B's frontend connects here for real-time rendering.

    Placeholder — Larris implements the actual streaming logic.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    async def event_generator():
        # ─── LARRIS IMPLEMENTS THIS ───
        # Yield report sections as they're generated:
        # yield f"data: {json.dumps(section.model_dump())}\\n\\n"
        #
        # For now, return a placeholder
        yield f"data: {json.dumps({'status': 'waiting', 'message': 'Generation engine pending'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.post("/api/case/{case_id}/edit-section")
async def edit_section(
    case_id: str,
    section_id: str = Form(...),
    instruction: str = Form(...),
):
    """
    Edit a specific report section via the side panel chatbot.
    User highlights a section, types an instruction, and this
    regenerates just that section.

    Placeholder — Larris implements the regeneration logic.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]

    # Find the section
    section = next(
        (s for s in case.report_sections if s.id == section_id),
        None,
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # ─── LARRIS IMPLEMENTS THIS ───
    # from app.services.generation.report import regenerate_section
    # updated = regenerate_section(case, section, instruction, index)
    # ──────────────────────────────

    return {
        "case_id": case_id,
        "section_id": section_id,
        "status": "regenerating",
        "instruction": instruction,
    }


@app.get("/api/case/{case_id}")
async def get_case(case_id: str):
    """
    Get the current state of a case.
    Used by Person B to render the full UI.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]

    return {
        "case_id": case.id,
        "title": case.title,
        "case_type": case.case_type,
        "description": case.description,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "evidence": [
            {
                "id": e.id,
                "filename": e.filename,
                "evidence_type": getattr(e.evidence_type, "value", e.evidence_type),
                "labels": e.labels,
                "summary": e.summary,
                "entity_count": len(e.entities),
            }
            for e in case.evidence
        ],
        "entities": [
            {
                "type": e.type,
                "name": e.name,
                "aliases": e.aliases,
                "mention_count": len(e.mentions),
            }
            for e in case.entities
        ],
        "contradictions": [
            {
                "id": c.id,
                "severity": getattr(c.severity, "value", c.severity),
                "description": c.description,
                "fact_a": c.fact_a,
                "fact_b": c.fact_b,
                "related_entities": c.related_entities,
            }
            for c in case.contradictions
        ],
        "report_sections": [
            {
                "id": s.id,
                "block_type": s.block_type.value,
                "order": s.order,
                "text": s.text,
                "heading_level": s.heading_level,
                "media": s.media.model_dump() if s.media else None,
                "citations": [c.model_dump() for c in s.citations],
                "is_edited": s.is_edited,
                "related_entities": s.related_entities,
            }
            for s in case.report_sections
        ],
        "generation_progress": case.generation_progress,
    }


@app.get("/api/case/{case_id}/entities/{entity_name}")
async def get_entity_details(case_id: str, entity_name: str):
    """
    Get all information about a specific entity across all evidence.
    Used by the "pick a witness" feature — shows every mention,
    every relevant fact, and every contradiction involving them.
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    index = citation_indices.get(case_id)

    # Find the entity
    entity = next(
        (e for e in case.entities if e.name.lower() == entity_name.lower()),
        None,
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get all facts about this entity from the citation index
    facts = []
    if index:
        indexed_facts = index.query_by_entity(entity_name)
        facts = [
            {
                "fact": f.fact_text,
                "dimension": f.dimension,
                "source_evidence_id": f.source_location.evidence_id,
                "page": f.source_location.page,
                "excerpt": f.excerpt,
                "reliability": f.reliability,
            }
            for f in indexed_facts
        ]

    # Get contradictions involving this entity
    from app.services.intelligence.contradictions import get_contradictions_for_entity
    entity_contradictions = get_contradictions_for_entity(case.contradictions, entity_name)

    return {
        "entity": {
            "type": entity.type,
            "name": entity.name,
            "aliases": entity.aliases,
            "mentions": [
                {
                    "evidence_id": m.evidence_id,
                    "page": m.page,
                    "timestamp_start": m.timestamp_start,
                    "excerpt": m.excerpt,
                }
                for m in entity.mentions
            ],
        },
        "facts": facts,
        "contradictions": [
            {
                "id": c.id,
                "severity": getattr(c.severity, "value", c.severity),
                "description": c.description,
                "fact_a": c.fact_a,
                "fact_b": c.fact_b,
            }
            for c in entity_contradictions
        ],
    }


# ──────────────────────────────────────────────
#  HEALTH CHECK
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "cases_in_memory": len(cases)}