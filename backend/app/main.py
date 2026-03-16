from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CLARION_SERVICE_MODE
from app.routers import cases, edit, export, generate, internal, reconstruction, system, upload, voice

app = FastAPI(
    title="Clarion API",
    description="AI-powered litigation visual engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.service_mode = CLARION_SERVICE_MODE

if CLARION_SERVICE_MODE in {"all", "api"}:
    app.include_router(upload.router, prefix="/upload", tags=["upload"])
    app.include_router(generate.router, prefix="/generate", tags=["generate"])
    app.include_router(edit.router, prefix="/edit", tags=["edit"])
    app.include_router(export.router, prefix="/export", tags=["export"])
    app.include_router(reconstruction.router, prefix="/reconstruction", tags=["reconstruction"])
    app.include_router(cases.router, prefix="/cases", tags=["cases"])
    app.include_router(voice.router, prefix="/voice", tags=["voice"])

if CLARION_SERVICE_MODE in {"all", "worker"}:
    app.include_router(internal.router, prefix="/internal", tags=["internal"])

app.include_router(system.router, tags=["system"])
