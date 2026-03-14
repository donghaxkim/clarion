# Report Agent Handoff

This project now has a working backend path for chronological report generation using Google ADK + Gemini, with optional public-context enrichment and optional image/video media attachments.

## What Exists

- `backend/app/routers/generate.py`
  - `POST /generate/jobs` creates a queued report job, stores the request payload in GCS, and dispatches a Cloud Task.
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
  - Firestore-backed report job store with SSE event history.
  - Report previews and canonical report JSON live in GCS.
  - Request payloads are stored in `report-jobs/{job_id}/request.json`.
- `backend/app/services/cloud/dispatch.py`
  - Cloud Tasks launcher that calls the Cloud Run Jobs API.
- `backend/app/workers.py`
  - Cloud Run Job entrypoint for `report` workers.
- `backend/app/services/generation/image_generator.py`
  - Gemini image generation path.
- `backend/app/services/generation/reconstruction_service.py`
  - Direct adapter into shared reconstruction generation without nested persisted jobs.

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
- `backend/.env.example` shows the cloud-backed setup.
- Important report settings:
  - `REPORT_TEXT_MODEL`
  - `REPORT_HELPER_MODEL`
  - `REPORT_IMAGE_MODEL`
  - `REPORT_SEARCH_MODEL`
  - `REPORT_ENABLE_PUBLIC_CONTEXT`
  - `REPORT_CONTEXT_CACHE_ENABLED`
  - `REPORT_MAX_IMAGES`
  - `REPORT_MAX_RECONSTRUCTIONS`
- Auth-related settings:
  - `GOOGLE_API_KEY`
  - `GEMINI_API_KEY`
  - `VERTEX_PROJECT_ID`
  - `VERTEX_LOCATION`
  - `GCP_PROJECT_ID`
  - `FIRESTORE_PROJECT_ID`
  - `FIRESTORE_DATABASE`
  - `GCS_BUCKET`
  - `GCS_SIGNED_URL_TTL_SECONDS`
  - `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`
  - `CLOUD_RUN_REGION`
  - `CLOUD_TASKS_PROJECT_ID`
  - `CLOUD_TASKS_LOCATION`
  - `CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL`
  - `REPORT_TASK_QUEUE`
  - `REPORT_WORKER_JOB_NAME`

## Private Artifact Delivery

- Report media, citations, and report JSON are now returned as private V4 signed URLs.
- The API service resolves the signer service account from `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`, or falls back to the runtime service account email when available.
- Deployment must enable `iamcredentials.googleapis.com`.
- The API runtime service account must have `roles/iam.serviceAccountTokenCreator` on `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`.
- If signed URL generation is misconfigured, report fetch endpoints return a clear 500 instead of silently omitting URLs or downgrading to unsigned public links.

Post-deploy validation:

1. Complete a report job with at least one citation or media artifact stored in GCS.
2. Call `GET /generate/jobs/{job_id}` or `GET /generate/reports/{report_id}`.
3. Confirm returned artifact URLs are HTTPS signed URLs containing `X-Goog-*` query parameters.
4. Open one returned URL from outside GCP and verify the object loads while the bucket remains private.

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
- Cloud Run request handlers no longer execute generation inline.
  - Workers must be provisioned as Cloud Run Jobs and dispatched through Cloud Tasks.
- Worker startup is idempotent at the job-store layer.
  - Duplicate task/job executions should claim-and-exit instead of rerunning the pipeline.
- Private artifact delivery depends on IAM URL signing being configured.
  - A completed job can still fail at fetch time if `SIGNED_URL_SERVICE_ACCOUNT_EMAIL` or `roles/iam.serviceAccountTokenCreator` is wrong.

## Current Limits

- Audio is not part of v1 report generation.
- The report-editing/chatbot follow-up flow does not exist yet.
- Job state depends on Firestore + GCS + Cloud Tasks + Cloud Run Jobs being configured.
- Evidence citation richness depends on the upstream bundle.
  - If upstream only provides evidence ids, citations will have sparse locator fields.
- Public-context grounding is present, but future agents may want to persist richer grounding metadata for UI use.
- Real image generation depends on project/model access.
  - Image failures currently degrade to warnings and omitted media blocks.
