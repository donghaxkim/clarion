# Reconstruction Handoff

This project now has a working backend path for AI video reconstruction.

## What Exists

- `backend/app/routers/reconstruction.py`
  - `POST /reconstruction/jobs` creates a job and starts background processing.
  - `GET /reconstruction/jobs/{job_id}` returns queued/running/completed/failed status.
- `backend/app/models/reconstruction.py`
  - Request/response models for reconstruction jobs.
  - Supports `fast_only` and `fast_then_final`.
- `backend/app/services/video/reconstruction/orchestrator.py`
  - Main flow: fast generation, optional final generation, upload, manifest write, job completion/failure.
- `backend/app/services/video/reconstruction/veo_client.py`
  - Real Veo call path via Gemini API or Vertex.
  - Supports reference images, polling, URI download handling, and fake mode when enabled.
- `backend/app/services/video/reconstruction/job_store.py`
  - File-backed job state store.
- `backend/app/utils/storage.py`
  - Real GCS upload/download path.
  - Optional local fallback path for development/testing.

## Config

- `backend/app/config.py` contains all reconstruction-related env settings.
- `backend/.env.example` shows the intended local-dev setup.
- Important toggles:
  - `VEO_ALLOW_FAKE`
  - `GCS_ALLOW_LOCAL_FALLBACK`
  - `GEMINI_API_KEY`
  - `VERTEX_PROJECT_ID`
  - `GCS_BUCKET`

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
- Reconstruction job state is local file storage, not a database.
- Real flow needs both generation credentials and real GCS access when fallbacks are off.
- Local artifact scratch paths are still used internally even in real mode for some download handling.
