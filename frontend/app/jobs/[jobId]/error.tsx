"use client";

import { RouteErrorState } from "@/app/_components/route-error-state";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteErrorState
      title="The live director console lost its footing."
      message="Clarion could not recover this job view. Retry, and if the failure continues, verify the report job still exists and the backend stream is reachable."
      reset={reset}
    />
  );
}
