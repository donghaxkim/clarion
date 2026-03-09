import type {
  CaseCreateResponse,
  UploadResponse,
  AnalyzeResponse,
  GenerateResponse,
  EntityDetail,
} from "./types";

const API_BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

export async function createCase(opts?: {
  title?: string;
  case_type?: string;
  description?: string;
}): Promise<CaseCreateResponse> {
  const form = new FormData();
  if (opts?.title) form.append("title", opts.title);
  if (opts?.case_type) form.append("case_type", opts.case_type);
  if (opts?.description) form.append("description", opts.description);
  const res = await fetch(`${API_BASE}/api/case/create`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`createCase failed: ${res.status}`);
  return res.json();
}

export async function uploadEvidence(
  caseId: string,
  files: File[]
): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch(`${API_BASE}/api/case/${caseId}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`uploadEvidence failed: ${res.status}`);
  return res.json();
}

export async function analyzeCase(caseId: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/case/${caseId}/analyze`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`analyzeCase failed: ${res.status}`);
  return res.json();
}

export async function generateReport(
  caseId: string
): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/api/case/${caseId}/generate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`generateReport failed: ${res.status}`);
  return res.json();
}

export async function editSection(
  caseId: string,
  sectionId: string,
  instruction: string
): Promise<{ section_id: string; content: string }> {
  const form = new FormData();
  form.append("section_id", sectionId);
  form.append("instruction", instruction);
  const res = await fetch(`${API_BASE}/api/case/${caseId}/edit-section`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`editSection failed: ${res.status}`);
  return res.json();
}

export async function getCase(caseId: string) {
  const res = await fetch(`${API_BASE}/api/case/${caseId}`);
  if (!res.ok) throw new Error(`getCase failed: ${res.status}`);
  return res.json();
}

export async function getEntity(
  caseId: string,
  entityName: string
): Promise<EntityDetail> {
  const res = await fetch(
    `${API_BASE}/api/case/${caseId}/entities/${encodeURIComponent(entityName)}`
  );
  if (!res.ok) throw new Error(`getEntity failed: ${res.status}`);
  return res.json();
}

export function createEventSource(streamId: string): EventSource {
  return new EventSource(`${API_BASE}/api/stream/${streamId}`);
}
