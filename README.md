# Clarion

Backend (Person A) + Frontend (Person B). Shared contract: `backend/app/models/schema.py`.

## Setup

- **Backend:** `cd backend && pip install -r ../requirements.txt && PYTHONPATH=. uvicorn app.main:app --reload`
- **Frontend:** `cd frontend && npm install && npm run dev`
- **Mock evidence:** Add test files under `mock-evidence/` (see README there).
