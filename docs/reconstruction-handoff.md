# Reconstruction Handoff

This project now has a working backend path for AI video reconstruction.

## What Exists

- `backend/app/routers/reconstruction.py`
  - `POST /reconstruction/jobs` creates a queued job, stores the request payload in GCS, and dispatches a Cloud Task.
  - `GET /reconstruction/jobs/{job_id}` returns queued/running/completed/failed status.
- `backend/app/models/reconstruction.py`
  - Request/response models for reconstruction jobs.
  - Supports `fast_only` and `fast_then_final`.
- `backend/app/services/video/reconstruction/orchestrator.py`
  - Main flow: fast generation, optional final generation, upload, manifest write, job completion/failure.
  - Shared `ReconstructionArtifactService` powers both persisted jobs and report-inline reconstructions.
- `backend/app/services/video/reconstruction/veo_client.py`
  - Real Veo call path via Gemini API or Vertex.
  - Supports reference images, polling, URI download handling, and fake mode when enabled.
- `backend/app/services/video/reconstruction/job_store.py`
  - Firestore-backed job state store.
  - Request payloads are stored in `reconstruction-jobs/{job_id}/request.json`.
- `backend/app/services/cloud/dispatch.py`
  - Cloud Tasks launcher that calls the Cloud Run Jobs API.
- `backend/app/workers.py`
  - Cloud Run Job entrypoint for `reconstruction` workers.
- `backend/app/utils/storage.py`
  - GCS upload/download + signed URL path only.

## Config

- `backend/app/config.py` contains all reconstruction-related env settings.
- `backend/.env.example` shows the cloud-backed setup.
- Important toggles:
  - `VEO_ALLOW_FAKE`
  - `GEMINI_API_KEY`
  - `VERTEX_PROJECT_ID`
  - `GCS_BUCKET`
  - `GCS_SIGNED_URL_TTL_SECONDS`
  - `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`
  - `FIRESTORE_PROJECT_ID`
  - `FIRESTORE_DATABASE`
  - `CLOUD_TASKS_PROJECT_ID`
  - `CLOUD_TASKS_LOCATION`
  - `CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL`
  - `RECONSTRUCTION_TASK_QUEUE`
  - `RECONSTRUCTION_WORKER_JOB_NAME`

## Private Artifact Delivery

- Completed reconstruction jobs now return private V4 signed URLs for `result.video_url`.
- The API service signs those URLs with `SIGNED_URL_SERVICE_ACCOUNT_EMAIL`, or the runtime service account if no override is set and the identity exposes an email.
- Deployment must enable `iamcredentials.googleapis.com`.
- The API runtime service account must have `roles/iam.serviceAccountTokenCreator` on the signer service account.
- The router no longer falls back to bare `https://storage.googleapis.com/...` links for private buckets.

Post-deploy validation:

1. Complete a reconstruction job.
2. Call `GET /reconstruction/jobs/{job_id}` and confirm `result.video_url` is an HTTPS URL with `X-Goog-Algorithm`, `X-Goog-Credential`, and `X-Goog-Signature`.
3. Fetch that URL from a browser or `curl` outside GCP and verify the video loads without making the bucket public.

## Testing

- Real-flow smoke test script:
  - `backend/scripts/test_real_reconstruction.sh`
- Reconstruction-focused tests:
  - `backend/tests/test_reconstruction_models.py`
  - `backend/tests/test_reconstruction_router.py`
  - `backend/tests/test_reconstruction_orchestrator.py`
  - `backend/tests/test_storage.py`
  - `backend/tests/test_veo_client.py`

## Current Limits

- `upload`, `generate`, `edit`, and `export` routes are still placeholders.
- Reconstruction job state depends on Firestore + GCS + Cloud Tasks + Cloud Run Jobs being configured.
- Real flow needs both generation credentials and real GCS access.
- Private artifact delivery also needs IAM URL-signing permissions.
- If `SIGNED_URL_SERVICE_ACCOUNT_EMAIL` or token-creator IAM is wrong, completed jobs will return a clear 500 when clients poll for the video URL.
- Veo downloads still use ephemeral temp files internally before upload, but no local filesystem path is authoritative state.
