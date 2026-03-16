import { ClarionApiError, openReportJobStream } from '@/lib/server/clarion-api';

export const runtime = 'nodejs';

interface RouteContext {
  params: {
    jobId: string;
  };
}

export async function GET(request: Request, { params }: RouteContext) {
  try {
    const upstream = await openReportJobStream(params.jobId, {
      Accept: 'text/event-stream',
      'Last-Event-ID': request.headers.get('last-event-id') ?? '',
      'Cache-Control': 'no-cache',
    });

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        'Content-Type':
          upstream.headers.get('content-type') ?? 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    const status = error instanceof ClarionApiError ? error.status : 500;
    const detail =
      error instanceof Error ? error.message : 'Unexpected report stream failure.';
    return new Response(JSON.stringify({ detail }), {
      status,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
}
