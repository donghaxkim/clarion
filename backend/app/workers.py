from __future__ import annotations

import argparse
import asyncio
import os


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clarion Cloud Run worker entrypoints")
    parser.add_argument("worker", choices=("report", "analysis", "reconstruction"))
    args = parser.parse_args(argv)

    if args.worker == "report":
        job_id = _require_env("CLARION_JOB_ID")
        return asyncio.run(run_report_worker(job_id))
    if args.worker == "analysis":
        case_id = _require_env("CLARION_CASE_ID")
        evidence_revision = int(_require_env("CLARION_EVIDENCE_REVISION"))
        return asyncio.run(run_analysis_worker(case_id, evidence_revision))
    job_id = _require_env("CLARION_JOB_ID")
    return asyncio.run(run_reconstruction_worker(job_id))


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set for worker execution")
    return value


async def run_report_worker(job_id: str) -> int:
    from app.services.intelligence_worker import execute_report_job

    await execute_report_job(job_id)
    return 0


async def run_analysis_worker(case_id: str, evidence_revision: int) -> int:
    from app.services.intelligence_worker import execute_case_analysis

    execute_case_analysis(case_id, evidence_revision=evidence_revision)
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
