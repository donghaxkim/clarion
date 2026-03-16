import { getClarionWebSocketBaseUrl } from '@/lib/server/clarion-api';

export async function GET() {
  return Response.json(
    {
      websocket_base_url: getClarionWebSocketBaseUrl(),
    },
    {
      headers: {
        'Cache-Control': 'no-store',
      },
    },
  );
}
