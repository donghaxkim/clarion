# FastAPI entry point
from fastapi import FastAPI
from app.routers import upload, generate, edit, export

app = FastAPI(title="Clarion API")
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(generate.router, prefix="/generate", tags=["generate"])
app.include_router(edit.router, prefix="/edit", tags=["edit"])
app.include_router(export.router, prefix="/export", tags=["export"])
