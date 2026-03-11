import { NextResponse } from "next/server";

import { ClarionApiError, getReport } from "@/lib/clarion-api";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{
    reportId: string;
  }>;
}

export async function GET(_: Request, { params }: RouteContext) {
  try {
    const { reportId } = await params;
    const report = await getReport(reportId);
    return NextResponse.json(report);
  } catch (error) {
    if (error instanceof ClarionApiError) {
      return NextResponse.json({ detail: error.message }, { status: error.status });
    }

    const detail =
      error instanceof Error ? error.message : "Unexpected report fetch failure.";
    return NextResponse.json({ detail }, { status: 500 });
  }
}
