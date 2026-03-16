# Clarion Project Spec

Version: 0.1  

## 1. Product Summary
Clarion is an AI-assisted legal report builder that ingests multimodal evidence and generates a courtroom-ready timeline report. The report supports mixed media blocks (text, images, video (later with audio narration)) and after it's generated, it allows targeted section edits through a chatbot on the side that appears when you highlight a section.

## 2. Core Workflow
1. User lands on the Clarion web app.
2. User submits case details and uploads evidence.
3. Clarion processes files and auto-labels evidence into categories for organization.
4. Clarion generates a structured chronological report with linked citations.
5. User highlights a specific report section; side chatbot opens context-aware edit mode and updates only that section.
6. User exports a presentation-ready courtroom report.

## 3. Supported Inputs (Multimodal Intake)
- PDFs
- Images
- Testimonies (text/transcripts from police, witnesses, etc.)
- Voice recordings
- Videos (ex. dashcam videos, security camera videos, etc.)
- Medical reports (ex. MRI reports, CT scans, etc.)

## 4. Primary Output
Clarion produces a rich, block-based report (Notion-style composition) that interleaves:
- Narrative text
- Images
- Video clips
- AI-generated recreations (video) of events (for example, crash reconstruction)
All with citations linked.

Note: Audio narration for recreation is planned but out of MVP scope.

## 5. Functional Requirements
### FR-1: Evidence Intake and Normalization
- System accepts all supported multimodal input types.
- Files receive unique IDs and metadata (source, upload time, type, confidence notes).

### FR-2: Auto-Labeling and Organization
- Clarion classifies evidence into categories (for example: incident media, witness evidence, medical evidence, official records).
- User can review and adjust labels.

### FR-3: Report Generation
- System generates a report from available evidence.
- Report structure supports interleaved text, images, and video blocks.
- Report sections store citation links to evidence sources.

### FR-4: Section-Scoped Chat Editing
- User can highlight a section and open a side chatbot.
- Chatbot edits are constrained to the selected section unless user explicitly broadens scope.
- Edited section maintains citation traceability.

### FR-5: Citations
- Claims in generated report include citation references.
- Citations are navigable back to source evidence segments.

### FR-6: Missing Information Detector (NOT MVP)
- System flags likely missing artifacts (for example, no medical record for claimed injury).
- Prompts user with a checklist of missing inputs.

### FR-7: Evidence Contradiction Detector (NOT MVP)
- System identifies conflicting witness or media-derived claims.
- Contradictions are listed with linked evidence and confidence scores.

### FR-8: Zoomable Timeline (NOT MVP)
- Report includes a timeline view that can zoom by granularity (hour/day/event segment).
- Timeline nodes link back to relevant report blocks and evidence items.

### FR-9: Person-Focused View (NOT MVP)
- User can select a person/entity (for example, "Witness 1").
- Clarion filters relevant evidence and report fragments.
- System generates a question outline for deposition/cross-examination prep.

### FR-10: Counter-Argument Weaving (NOT MVP)
- Clarion can interleave opposing interpretations directly in report sections.
- Counter-arguments are tagged and citation-backed.

### FR-11: Courtroom-Ready Export (NOT MVP)
- Export formats are presentation-safe (PDF in MVP, additional formats later).
- Export preserves section order, citations, timeline references, and embedded media references.

### FR-12: Live Generation Status (NOT MVP)
- UI shows real-time status for intake, labeling, contradiction scan, and report synthesis.
- User can monitor progress without refreshing.
