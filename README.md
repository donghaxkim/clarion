# Clarion

**Clarion** is an AI-powered litigation tool. It takes case evidence (PDFs, audio, images), parses and analyzes it, then:

1. **Indexes facts** — Builds a citation index so you can find and reference specific claims across documents.
2. **Finds contradictions** — Flags conflicting statements between sources (e.g. witness vs report).
3. **Generates reports** — Produces courtroom-ready reports you can stream, edit via chat, and export. Reports can include **AI-generated video** — scene reconstructions generated from witness descriptions (e.g. from testimony or statements), so you can present a visual version of the described events in court.

You create a case, upload evidence, and use the REST API (or future frontend) to generate reports, see contradictions, and include witness-based scene videos where needed. A **voice agent** (push-to-talk over WebSocket) lets you ask case questions and edit report sections via speech. Optional Google Gemini is used for summarization, analysis, and the voice agent; mocks are available for testing without an API key.

---

## Quick start

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in GCP / Firestore / Cloud Tasks / GCS settings
PYTHONPATH=. uvicorn app.main:app --reload
```

- API: **http://127.0.0.1:8000**  
- Docs: **http://127.0.0.1:8000/docs**

---

## Tech

- **Backend:** Python, FastAPI, Pydantic  
- **AI:** Google Gemini (optional)  
- **Storage:** Firestore for job metadata, GCS for report artifacts and job payloads
- **Execution:** Cloud Tasks dispatches a warm Cloud Run worker service for report and analysis; reconstruction remains on a separate Cloud Run Job

## Report Workflow

```mermaid
flowchart TD
    U["User / Experience UI"] --> API["clarion-api<br/>POST /cases/{caseId}/report-jobs"]
    API --> STORE["ReportJobStore<br/>create queued job + save request"]
    API --> TASKS["Cloud Tasks<br/>enqueue report task"]
    TASKS --> WORKER["clarion-intelligence-worker<br/>POST /internal/report-jobs/{job_id}"]
    WORKER --> ORCH["ReportGenerationOrchestrator.run_job(...)"]
    ORCH --> STORE

    ORCH --> ADKRT["AdkReportingPipeline.run(...)"]

    subgraph ADK["ADK + Gemini reporting workflow"]
        PLANNER["TimelinePlannerAgent<br/>Gemini text model"]
        GREVIEW["GroundingReviewerAgent<br/>Gemini text model"]
        GREFINE["TimelineRefinerAgent<br/>Gemini text model"]
        CTX["ContextEnrichmentAgent<br/>Gemini helper + Google Search"]
        MEDIA["MediaPlannerAgent<br/>Gemini helper"]
        COMPOSER["FinalComposerAgent<br/>Gemini text model"]
        CREVIEW["CompositionReviewerAgent<br/>Gemini helper"]
        CREFINE["CompositionRefinerAgent<br/>Gemini text model"]
        RESULT["PipelineResult<br/>blocks + image_requests + reconstruction_requests"]
    end

    ADKRT --> PLANNER
    PLANNER --> GREVIEW
    GREVIEW -- "issues found" --> GREFINE
    GREFINE --> GREVIEW
    GREVIEW -- "approved" --> CTX
    GREVIEW -- "approved" --> MEDIA
    CTX --> COMPOSER
    MEDIA --> COMPOSER
    COMPOSER --> CREVIEW
    CREVIEW -- "issues found" --> CREFINE
    CREFINE --> CREVIEW
    CREVIEW -- "approved" --> RESULT

    ADKRT -- "ADK failure" --> FALLBACK["HeuristicReportingPipeline"]
    FALLBACK --> RESULT

    RESULT --> REPORT["create_initial_report(...)<br/>text blocks + media placeholders"]

    subgraph MEDIAEXEC["Media execution"]
        IMG["GeminiImageGenerator<br/>Imagen"]
        RECON["ReconstructionMediaService<br/>Veo"]
        IMGASSET["image asset + manifest"]
        VIDASSET["video asset + manifest"]
    end

    RESULT --> IMG
    RESULT --> RECON
    IMG --> IMGASSET
    RECON --> VIDASSET

    IMGASSET --> ATTACH["attach_media_asset(...)"]
    VIDASSET --> ATTACH
    ATTACH --> FINAL["finalize_report(...)<br/>persist report.json + manifest"]
    FINAL --> STORE

    STORE --> STATUS["GET /generate/jobs/{job_id}<br/>SSE + polling"]
    STATUS --> U
```

## Private GCS artifact delivery

Cloud Run serves report and reconstruction artifacts from a private GCS bucket by
generating V4 signed URLs at request time.

- Set `SIGNED_URL_SERVICE_ACCOUNT_EMAIL` to the service account that should sign artifact URLs.
- Enable `iamcredentials.googleapis.com` in the same project as the signer.
- Grant the API runtime service account `roles/iam.serviceAccountTokenCreator` on `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`.
- Keep the bucket private. Clarion now expects signed URLs instead of public `storage.googleapis.com` links.

Post-deploy validation:

1. Submit a reconstruction or report job until it reaches `completed`.
2. Call the polling/report endpoint and confirm the returned artifact URL is HTTPS and includes `X-Goog-Algorithm`, `X-Goog-Credential`, and `X-Goog-Signature`.
3. Fetch that URL from your browser or `curl` outside GCP and confirm the object loads without making the bucket public.

For full API reference, project structure, and schema details, see the in-repo docs or `backend/app/models/schema.py`.
