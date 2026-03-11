import { NextResponse } from "next/server";

import { ClarionApiError, getReportJob } from "@/lib/clarion-api";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(_: Request, { params }: RouteContext) {
  try {
    const { jobId } = await params;
    const job = await getReportJob(jobId);
    return NextResponse.json(job);
  } catch (error) {
    if (error instanceof ClarionApiError) {
      return NextResponse.json({ detail: error.message }, { status: error.status });
    }

    const detail =
      error instanceof Error ? error.message : "Unexpected report status failure.";
    return NextResponse.json({ detail }, { status: 500 });
  }
}
