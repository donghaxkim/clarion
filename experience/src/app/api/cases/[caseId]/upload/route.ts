import { ClarionApiError, fetchClarion, toJsonProxyResponse } from '@/lib/server/clarion-api';

export const runtime = 'nodejs';

interface RouteContext {
  params: {
    caseId: string;
  };
}

export async function POST(request: Request, { params }: RouteContext) {
  try {
    const incoming = await request.formData();
    const upstream = new FormData();
    for (const [key, value] of incoming.entries()) {
      if (typeof value === 'string') {
        upstream.append(key, value);
      } else {
        upstream.append(key, value, value.name);
      }
    }

    const response = await fetchClarion(`/upload/cases/${params.caseId}`, {
      method: 'POST',
      body: upstream,
    });
    return await toJsonProxyResponse(response);
  } catch (error) {
    return buildErrorResponse(error);
  }
}

function buildErrorResponse(error: unknown) {
  const status = error instanceof ClarionApiError ? error.status : 500;
  const detail =
    error instanceof Error ? error.message : 'Unexpected Clarion upload proxy failure.';
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}
