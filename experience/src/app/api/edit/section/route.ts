import { ClarionApiError, fetchClarion, toJsonProxyResponse } from '@/lib/server/clarion-api';

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const response = await fetchClarion('/edit/section', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
    });
    return await toJsonProxyResponse(response);
  } catch (error) {
    const status = error instanceof ClarionApiError ? error.status : 500;
    const detail =
      error instanceof Error ? error.message : 'Unexpected Clarion edit proxy failure.';
    return new Response(JSON.stringify({ detail }), {
      status,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
}
