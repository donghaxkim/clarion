from __future__ import annotations

import argparse
import asyncio
import os


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clarion Cloud Run worker entrypoints")
    parser.add_argument("worker", choices=("report", "reconstruction"))
    args = parser.parse_args(argv)

    job_id = os.getenv("CLARION_JOB_ID", "").strip()
    if not job_id:
        raise RuntimeError("CLARION_JOB_ID must be set for worker execution")

    if args.worker == "report":
        return asyncio.run(run_report_worker(job_id))
    return asyncio.run(run_reconstruction_worker(job_id))


async def run_report_worker(job_id: str) -> int:
    from app.services.generation import ReportGenerationOrchestrator, ReportJobStore

    store = ReportJobStore()
    if not store.claim_job(job_id):
        return 0
    payload = store.load_request(job_id)
    orchestrator = ReportGenerationOrchestrator(job_store=store)
    await orchestrator.run_job(job_id, payload)
    return 0


async def run_reconstruction_worker(job_id: str) -> int:
    from app.config import VEO_ALLOW_FAKE
    from app.services.video.reconstruction import (
        ReconstructionJobStore,
        ReconstructionOrchestrator,
        VeoClient,
    )

    store = ReconstructionJobStore()
    if not store.claim_job(job_id):
        return 0
    payload = store.load_request(job_id)
    orchestrator = ReconstructionOrchestrator(
        job_store=store,
        veo_client=VeoClient(allow_fake=VEO_ALLOW_FAKE),
    )
    await orchestrator.run_job(job_id, payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
