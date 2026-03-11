import { NextResponse } from "next/server";

import {
  ClarionApiError,
  createDemoReportJob,
  createReportJob,
} from "@/lib/clarion-api";
import type { GenerateReportRequest } from "@/lib/clarion-types";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const payload = await readPayload(request);
    const job = payload ? await createReportJob(payload) : await createDemoReportJob();
    return NextResponse.json(job, { status: 202 });
  } catch (error) {
    return toErrorResponse(error);
  }
}

async function readPayload(
  request: Request,
): Promise<GenerateReportRequest | null> {
  const contentLength = request.headers.get("content-length");
  if (!contentLength || contentLength === "0") {
    return null;
  }

  try {
    return (await request.json()) as GenerateReportRequest;
  } catch {
    return null;
  }
}

function toErrorResponse(error: unknown) {
  if (error instanceof ClarionApiError) {
    return NextResponse.json({ detail: error.message }, { status: error.status });
  }

  const detail =
    error instanceof Error ? error.message : "Unexpected report launch failure.";
  return NextResponse.json({ detail }, { status: 500 });
}
