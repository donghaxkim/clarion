import { ClarionApiError, fetchClarion, toJsonProxyResponse } from '@/lib/server/clarion-api';

interface RouteContext {
  params: {
    caseId: string;
  };
}

export async function GET(_request: Request, { params }: RouteContext) {
  try {
    const response = await fetchClarion(`/cases/${params.caseId}`);
    return await toJsonProxyResponse(response);
  } catch (error) {
    return buildErrorResponse(error);
  }
}

function buildErrorResponse(error: unknown) {
  const status = error instanceof ClarionApiError ? error.status : 500;
  const detail =
    error instanceof Error ? error.message : 'Unexpected Clarion proxy failure.';
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}
