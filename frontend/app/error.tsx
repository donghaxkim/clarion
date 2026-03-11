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
      title="The report surface hit an unexpected fault."
      message="Clarion could not finish rendering this route. Retry the request, and if it persists, confirm the backend and proxy routes are running."
      reset={reset}
    />
  );
}
