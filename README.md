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
pip install -r ../requirements.txt
cp ../.env.example ../.env   # add GOOGLE_API_KEY if using Gemini
PYTHONPATH=. uvicorn app.main:app --reload
```

- API: **http://127.0.0.1:8000**  
- Docs: **http://127.0.0.1:8000/docs**

---

## Tech

- **Backend:** Python, FastAPI, Pydantic  
- **AI:** Google Gemini (optional); voice agent via Gemini Live API (WebSocket)  
- **Storage:** Local uploads by default; schema supports GCS URLs  

For full API reference, project structure, and schema details, see the in-repo docs or `backend/app/models/schema.py`.