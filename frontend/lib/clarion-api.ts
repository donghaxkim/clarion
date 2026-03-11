import "server-only";

import { demoReportRequest } from "@/lib/clarion-demo";
import type {
  GenerateReportJobAcceptedResponse,
  GenerateReportRequest,
  ReportDocument,
  ReportGenerationJobStatusResponse,
} from "@/lib/clarion-types";

const clarionApiBaseUrl = (
  process.env.CLARION_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ClarionApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ClarionApiError";
    this.status = status;
  }
}

export async function fetchClarion(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  try {
    return await fetch(`${clarionApiBaseUrl}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch (error) {
    const message =
      error instanceof Error && error.message
        ? error.message
        : "Unknown backend connectivity failure";
    throw new ClarionApiError(
      `Clarion API did not respond. Set CLARION_API_BASE_URL and start the backend. ${message}`,
      503,
    );
  }
}

export async function createDemoReportJob() {
  return createReportJob(demoReportRequest);
}

export async function createReportJob(
  payload: GenerateReportRequest,
): Promise<GenerateReportJobAcceptedResponse> {
  const response = await fetchClarion("/generate/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return readJsonResponse<GenerateReportJobAcceptedResponse>(response);
}

export async function getReportJob(
  jobId: string,
): Promise<ReportGenerationJobStatusResponse> {
  const response = await fetchClarion(`/generate/jobs/${jobId}`);
  return readJsonResponse<ReportGenerationJobStatusResponse>(response);
}

export async function getReport(reportId: string): Promise<ReportDocument> {
  const response = await fetchClarion(`/generate/reports/${reportId}`);
  return readJsonResponse<ReportDocument>(response);
}

export async function openReportJobStream(
  jobId: string,
  headers?: HeadersInit,
): Promise<Response> {
  const response = await fetchClarion(`/generate/jobs/${jobId}/stream`, {
    headers,
  });

  if (!response.ok) {
    await throwResponseError(response);
  }

  if (!response.body) {
    throw new ClarionApiError("Clarion API returned an empty event stream.", 502);
  }

  return response;
}

export async function readJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    await throwResponseError(response);
  }

  return (await response.json()) as T;
}

async function throwResponseError(response: Response): Promise<never> {
  const message = await readErrorMessage(response);
  throw new ClarionApiError(message, response.status);
}

async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `Clarion API request failed with status ${response.status}.`;
  const text = await response.text();

  if (!text) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(text) as { detail?: string; error?: string };
    return parsed.detail ?? parsed.error ?? text;
  } catch {
    return text;
  }
}
