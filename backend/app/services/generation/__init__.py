from __future__ import annotations

__all__ = [
    "GeminiImageGenerator",
    "ReconstructionMediaService",
    "ReportGenerationOrchestrator",
    "ReportJobStore",
]


def __getattr__(name: str):
    if name == "GeminiImageGenerator":
        from app.services.generation.image_generator import GeminiImageGenerator

        return GeminiImageGenerator
    if name == "ReconstructionMediaService":
        from app.services.generation.reconstruction_service import ReconstructionMediaService

        return ReconstructionMediaService
    if name == "ReportGenerationOrchestrator":
        from app.services.generation.orchestrator import ReportGenerationOrchestrator

        return ReportGenerationOrchestrator
    if name == "ReportJobStore":
        from app.services.generation.job_store import ReportJobStore

        return ReportJobStore
    raise AttributeError(name)
