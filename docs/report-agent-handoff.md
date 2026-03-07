# Report Agent Handoff

This project now has a working backend path for chronological report generation using Google ADK + Gemini, with optional public-context enrichment and optional image/video media attachments.

## What Exists

- `backend/app/routers/generate.py`
  - `POST /generate/jobs` creates a report job and starts background processing.
  - `GET /generate/jobs/{job_id}` returns queued/planning/composing/generating_media/completed/failed status.
  - `GET /generate/jobs/{job_id}/stream` streams SSE job events.
  - `GET /generate/reports/{report_id}` returns the final report document.
- `backend/app/models/schema.py`
  - Defines the report contract:
    - `CaseEvidenceBundle`
    - `GenerateReportRequest`
    - `Citation`
    - `ReportBlock`
    - `ReportDocument`
    - report job status/event models
- `backend/app/agents/reporting/`
  - `agent_builder.py`
    - Builds the ADK workflow:
      - `TimelinePlannerAgent`
      - `GroundingReviewLoop`
      - parallel `ContextEnrichmentAgent` + `MediaPlannerAgent`
      - `FinalComposerAgent`
  - `runtime.py`
    - Selects the ADK pipeline when ADK + Gemini are available and credentials exist.
    - Falls back to the deterministic pipeline otherwise.
  - `callbacks.py`
    - Injects generation policy into model instructions.
    - Validates final composer output.
  - `validators.py`
    - Validates timeline/composer output.
    - Normalizes missing evidence citations for timeline/event blocks from the reviewed timeline state.
  - `fallback.py`
    - Deterministic non-ADK fallback for local/test use.
- `backend/app/services/generation/orchestrator.py`
  - Main flow:
    - publish `job.started`
    - run reporting pipeline
    - assemble initial report
    - emit `timeline.ready` and `block.created`
    - attempt media generation
    - persist report + manifest
    - mark job completed/failed
- `backend/app/services/generation/report.py`
  - Deterministic assembly helpers for report blocks/media attachment/finalization.
- `backend/app/services/generation/job_store.py`
  - File-backed report job store with SSE event history.
- `backend/app/services/generation/image_generator.py`
  - Gemini image generation path.
- `backend/app/services/generation/reconstruction_service.py`
  - Adapter into the existing reconstruction pipeline.

## Current ADK Flow

- Main evidence-grounded chronology is generated from `CaseEvidenceBundle`.
- Public context is emitted as separate `public_context` blocks, never mixed into evidence blocks.
- Media planning is selective:
  - image requests are optional
  - reconstruction requests are optional
- Media failures are non-fatal:
  - failed image/video blocks are omitted from the report
  - warnings are recorded in the final report

## Config

- `backend/app/config.py` contains all report-generation env settings.
- `backend/.env.example` shows the intended local-dev setup.
- Important report settings:
  - `REPORT_TEXT_MODEL`
  - `REPORT_HELPER_MODEL`
  - `REPORT_IMAGE_MODEL`
  - `REPORT_SEARCH_MODEL`
  - `REPORT_ENABLE_PUBLIC_CONTEXT`
  - `REPORT_CONTEXT_CACHE_ENABLED`
  - `REPORT_MAX_IMAGES`
  - `REPORT_MAX_RECONSTRUCTIONS`
  - `REPORT_JOB_STORE_PATH`
- Auth-related settings:
  - `GOOGLE_API_KEY`
  - `GEMINI_API_KEY`
  - `VERTEX_PROJECT_ID`
  - `VERTEX_LOCATION`
  - `GCS_BUCKET`
  - `GCS_ALLOW_LOCAL_FALLBACK`

## Testing

- Real-flow smoke test script:
  - `backend/scripts/test_real_report_generation.sh`
- Report-focused tests:
  - `backend/tests/test_report_models.py`
  - `backend/tests/test_reporting_pipeline.py`
  - `backend/tests/test_report_orchestrator.py`
  - `backend/tests/test_generate_router.py`

## Known Gotchas

- ADK app names must be valid Python identifiers.
  - Use `clarion_reporting`, not `clarion-reporting`.
- ADK callback signatures use `callback_context`.
  - Using another parameter name caused runtime callback errors.
- `system_instruction` may arrive as a raw string.
  - Do not assume `.parts` exists.
- `time_range_ms` must be a 2-item integer list, not a tuple.
  - Tuple JSON schema emitted `prefixItems`, which Gemini/ADK rejected.
- ADK automatic function-call schema parsing did not like `str | None` in output models.
  - Reporting output models were changed to `Optional[...]`.
- Public context search uses a wrapped search tool path.
  - Direct built-in `google_search` with the context agent caused compatibility issues.
  - The current path uses `GoogleSearchAgentTool` with `REPORT_SEARCH_MODEL` defaulting to `gemini-2.5-flash`.
- Final composer output may omit citations on synthetic timeline/event blocks.
  - `validators.normalize_composer_output()` backfills those from the reviewed timeline state.
- The file-backed job store is authoritative for job/report lookup.
  - `backend/.report_jobs.json` is expected in local/dev mode.

## Current Limits

- Audio is not part of v1 report generation.
- The report-editing/chatbot follow-up flow does not exist yet.
- Job state is local file storage, not a database.
- Evidence citation richness depends on the upstream bundle.
  - If upstream only provides evidence ids, citations will have sparse locator fields.
- Public-context grounding is present, but future agents may want to persist richer grounding metadata for UI use.
- Real image generation depends on project/model access.
  - Image failures currently degrade to warnings and omitted media blocks.
