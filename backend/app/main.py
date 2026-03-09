"""
CLARION — FastAPI Application
===============================
Main entry point. All routes use schema v2.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import os
from datetime import datetime

from app.models.schema import CaseFile, _id
from app.services.parser.labeler import parse_evidence, detect_file_type
from app.services.intelligence.citations import build_citation_index, CitationIndex
from app.services.intelligence.contradictions import detect_contradictions, summarize_contradictions
from app.services.intelligence.missing_info import detect_missing_info

app = FastAPI(title="Clarion API", description="AI-powered litigation visual engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cases: dict[str, CaseFile] = {}
citation_indices: dict[str, CitationIndex] = {}

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/clarion-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_upload(file: UploadFile) -> tuple[str, str]:
    file_id = _id()
    filename = file.filename or f"upload_{file_id}"
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    with open(local_path, "wb") as f:
        content = await file.read()
        f.write(content)
    media_url = f"file://{local_path}"
    return local_path, media_url


@app.post("/api/case/create")
async def create_case(
    title: Optional[str] = Form(None),
    case_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    case = CaseFile(title=title, case_type=case_type, intake_summary=description, status="intake")
    cases[case.id] = case
    return {"case_id": case.id, "status": case.status, "created_at": case.created_at.isoformat()}


@app.post("/api/case/{case_id}/upload")
async def upload_evidence(case_id: str, files: list[UploadFile] = File(...)):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    case.status = "parsing"

    results = []
    video_files = []

    for file in files:
        local_path, media_url = await save_upload(file)
        filename = file.filename or "unknown"
        file_type = detect_file_type(filename)

        if file_type == "video":
            video_files.append({
                "filename": filename,
                "local_path": local_path,
                "media_url": media_url,
                "status": "pending_video_analysis",
            })
            continue

        try:
            evidence = parse_evidence(local_path, filename, media_url)

            if evidence:
                case.evidence.append(evidence)

                for entity in evidence.entities:
                    existing = next(
                        (e for e in case.entities if e.name.lower() == entity.name.lower()),
                        None,
                    )
                    if existing:
                        existing.aliases = list(set(existing.aliases + entity.aliases))
                    else:
                        case.entities.append(entity)

                results.append({
                    "evidence_id": evidence.id,
                    "filename": evidence.filename,
                    "evidence_type": evidence.evidence_type,
                    "labels": evidence.labels,
                    "summary": evidence.summary,
                    "entity_count": len(evidence.entities),
                    "entities": [{"type": e.type, "name": e.name} for e in evidence.entities],
                    "status": "parsed",
                })
            else:
                results.append({"filename": filename, "status": "parse_failed", "error": "Could not parse file"})

        except Exception as e:
            results.append({"filename": filename, "status": "parse_failed", "error": str(e)})

    case.status = "intake"
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
    Run the full intelligence layer:
      1. Build citation index (discover dimensions + classify facts)
      2. Detect contradictions
      3. Detect missing info / evidence gaps
    """
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]

    if len(case.evidence) == 0:
        raise HTTPException(status_code=400, detail="No evidence uploaded yet")

    case.status = "analyzing"

    # 1. Build citation index
    index = build_citation_index(case)
    citation_indices[case_id] = index

    # 2. Detect contradictions
    contradictions = detect_contradictions(case, index)
    case.contradictions = contradictions

    # 3. Detect missing info
    missing = detect_missing_info(case, index)
    case.missing_info = missing

    case.status = "analyzing"
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
            {"id": e.id, "type": e.type, "name": e.name}
            for e in case.entities
        ],
        "contradictions": {
            "summary": summarize_contradictions(contradictions),
            "items": [
                {
                    "id": c.id,
                    "severity": c.severity,
                    "description": c.description,
                    "fact_a": c.fact_a,
                    "fact_b": c.fact_b,
                }
                for c in contradictions
            ],
        },
        "missing_info": {
            "total": len(missing),
            "critical": sum(1 for m in missing if m.severity == "critical"),
            "items": [
                {
                    "id": m.id,
                    "severity": m.severity,
                    "description": m.description,
                    "recommendation": m.recommendation,
                }
                for m in missing
            ],
        },
    }


@app.post("/api/case/{case_id}/generate")
async def generate_report(case_id: str):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")
    if case_id not in citation_indices:
        raise HTTPException(status_code=400, detail="Case not analyzed yet. Call /analyze first.")

    cases[case_id].status = "generating"

    # ─── LARRIS IMPLEMENTS THIS ───
    return {
        "case_id": case_id,
        "status": "generating",
        "message": "Report generation started. Connect to SSE stream for real-time updates.",
        "stream_url": f"/api/stream/{case_id}",
    }


@app.get("/api/stream/{case_id}")
async def stream_report(case_id: str):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    async def event_generator():
        # ─── LARRIS IMPLEMENTS THIS ───
        yield f"data: {json.dumps({'event': 'status', 'status': 'waiting', 'message': 'Generation engine pending'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/case/{case_id}/edit-section")
async def edit_section(case_id: str, section_id: str = Form(...), instruction: str = Form(...)):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    section = next((s for s in case.report_sections if s.id == section_id), None)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # ─── LARRIS IMPLEMENTS THIS ───
    return {"case_id": case_id, "section_id": section_id, "status": "regenerating", "instruction": instruction}


@app.get("/api/case/{case_id}")
async def get_case(case_id: str):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]

    return {
        "case_id": case.id,
        "title": case.title,
        "case_type": case.case_type,
        "intake_summary": case.intake_summary,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "evidence": [
            {
                "id": e.id,
                "filename": e.filename,
                "evidence_type": e.evidence_type,
                "labels": e.labels,
                "summary": e.summary,
                "entity_count": len(e.entities),
            }
            for e in case.evidence
        ],
        "entities": [
            {"id": e.id, "type": e.type, "name": e.name, "aliases": e.aliases}
            for e in case.entities
        ],
        "contradictions": [
            {
                "id": c.id,
                "severity": c.severity,
                "description": c.description,
                "fact_a": c.fact_a,
                "fact_b": c.fact_b,
            }
            for c in case.contradictions
        ],
        "missing_info": [
            {
                "id": m.id,
                "severity": m.severity,
                "description": m.description,
                "recommendation": m.recommendation,
            }
            for m in case.missing_info
        ],
        "report_sections": [s.model_dump() for s in case.report_sections],
    }


@app.get("/api/case/{case_id}/entities/{entity_name}")
async def get_entity_details(case_id: str, entity_name: str):
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="Case not found")

    case = cases[case_id]
    index = citation_indices.get(case_id)

    entity = next((e for e in case.entities if e.name.lower() == entity_name.lower()), None)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    facts = []
    if index:
        for f in index.query_by_entity(entity_name):
            facts.append({
                "fact": f.fact_text,
                "dimension": f.dimension,
                "evidence_id": f.evidence_id,
                "excerpt": f.excerpt,
                "reliability": f.reliability,
            })

    from app.services.intelligence.contradictions import get_contradictions_for_entity
    entity_contradictions = get_contradictions_for_entity(case.contradictions, entity_name)

    return {
        "entity": {"id": entity.id, "type": entity.type, "name": entity.name, "aliases": entity.aliases},
        "facts": facts,
        "contradictions": [
            {"id": c.id, "severity": c.severity, "description": c.description, "fact_a": c.fact_a, "fact_b": c.fact_b}
            for c in entity_contradictions
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "cases_in_memory": len(cases)}