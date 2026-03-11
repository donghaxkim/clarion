"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import type { GenerateReportJobAcceptedResponse } from "@/lib/clarion-types";

export function LaunchDemoButton() {
  const router = useRouter();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function handleLaunch() {
    setErrorMessage(null);

    try {
      const response = await fetch("/api/report-jobs", {
        method: "POST",
      });

      if (!response.ok) {
        const detail = await readResponseDetail(response);
        throw new Error(detail);
      }

      const job =
        (await response.json()) as GenerateReportJobAcceptedResponse;

      startTransition(() => {
        router.push(`/jobs/${job.job_id}`);
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Clarion could not reach the backend. Start the API and try again.",
      );
    }
  }

  return (
    <div className="max-w-xl">
      <button
        type="button"
        onClick={handleLaunch}
        disabled={isPending}
        className="inline-flex min-h-14 items-center justify-center rounded-full border border-amber/40 bg-amber px-7 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-ink transition-transform transition-colors duration-200 hover:-translate-y-0.5 hover:bg-amber-soft disabled:cursor-wait disabled:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
      >
        {isPending ? `Launching Demo${"\u2026"}` : "Launch Demo Case"}
      </button>
      <p
        className="mt-4 min-h-6 text-sm leading-6 text-paper/68"
        aria-live="polite"
      >
        {errorMessage ??
          "Runs the built-in case against the real backend and opens the live director console."}
      </p>
    </div>
  );
}

async function readResponseDetail(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "Clarion could not launch the demo case.";
  } catch {
    return "Clarion could not launch the demo case.";
  }
}
