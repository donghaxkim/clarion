import { ClarionApiError, openReportJobStream } from "@/lib/clarion-api";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(request: Request, { params }: RouteContext) {
  try {
    const { jobId } = await params;
    const upstream = await openReportJobStream(jobId, {
      Accept: "text/event-stream",
      "Last-Event-ID": request.headers.get("last-event-id") ?? "",
      "Cache-Control": "no-cache",
    });

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ?? "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    if (error instanceof ClarionApiError) {
      return new Response(JSON.stringify({ detail: error.message }), {
        status: error.status,
        headers: {
          "Content-Type": "application/json",
        },
      });
    }

    const detail =
      error instanceof Error ? error.message : "Unexpected report stream failure.";
    return new Response(JSON.stringify({ detail }), {
      status: 500,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }
}
