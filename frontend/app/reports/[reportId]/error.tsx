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
      title="The shareable report view failed to load."
      message="Clarion could not render this report route. Retry, and if it persists, confirm the report still exists in the backend job store."
      reset={reset}
    />
  );
}
