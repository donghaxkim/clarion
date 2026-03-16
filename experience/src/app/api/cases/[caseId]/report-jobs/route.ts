import { ClarionApiError, fetchClarion, toJsonProxyResponse } from '@/lib/server/clarion-api';

interface RouteContext {
  params: {
    caseId: string;
  };
}

export async function POST(_request: Request, { params }: RouteContext) {
  try {
    const response = await fetchClarion(`/cases/${params.caseId}/report-jobs`, {
      method: 'POST',
    });
    return await toJsonProxyResponse(response);
  } catch (error) {
    return buildErrorResponse(error);
  }
}

function buildErrorResponse(error: unknown) {
  const status = error instanceof ClarionApiError ? error.status : 500;
  const detail =
    error instanceof Error ? error.message : 'Unexpected Clarion report-job proxy failure.';
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}
