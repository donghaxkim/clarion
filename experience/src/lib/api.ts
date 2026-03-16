'use client';

import {
  adaptAnalysisResponse,
  adaptCaseReportState,
  adaptCaseResponse,
  adaptEntityDetailResponse,
  adaptGenerateResponse,
  adaptReportJobSnapshot,
  adaptReportSections,
  adaptUploadResponse,
} from './adapters';
import type {
  GenerateReportJobAcceptedResponse,
  ReportDocument,
  ReportGenerationJobStatusResponse,
} from './clarion-types';
import {
  MOCK_ANALYSIS,
  MOCK_CASE_ID,
  MOCK_CASE_TITLE,
  MOCK_ENTITY_DETAILS,
  MOCK_EVIDENCE,
  MOCK_FULL_CASE,
  MOCK_REPORT_SECTIONS,
} from './mock-data';
import type {
  AnalysisResponse,
  CaseReportState,
  CreateCaseResponse,
  EditSectionResponse,
  EntityDetailResponse,
  FullCase,
  GenerateResponse,
  ParsedEvidence,
  ReportJobSnapshot,
  ReportSection,
  UploadResponse,
} from './types';

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const API_BASE = '/api';
const REPORT_STREAM_EVENTS = [
  'job.started',
  'timeline.ready',
  'block.created',
  'block.updated',
  'media.started',
  'media.completed',
  'job.activity',
  'report.preview.updated',
];
const REPORT_STREAM_TERMINAL_EVENTS = ['job.completed', 'job.failed'];

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return (await response.json()) as T;
}

async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `Request failed with status ${response.status}.`;
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

function buildMockCaseReportState(caseId: string): CaseReportState {
  return {
    case_id: caseId,
    job_id: 'mock-report-job',
    report_id: 'mock-report',
    status: 'completed',
    progress: 100,
    warnings: [],
    error: null,
    report_sections: MOCK_REPORT_SECTIONS,
    activity: null,
  };
}

export async function createCase(opts?: {
  title?: string;
  case_type?: string;
  description?: string;
}): Promise<CreateCaseResponse> {
  if (USE_MOCK) {
    await delay(200);
    return {
      case_id: MOCK_CASE_ID,
      status: 'created',
      created_at: new Date().toISOString(),
    };
  }

  return fetchJson<CreateCaseResponse>('/cases', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: opts?.title,
      case_type: opts?.case_type,
      description: opts?.description,
    }),
  });
}

export async function uploadFiles(
  caseId: string,
  files: File[],
  onProgress?: (evidence: ParsedEvidence) => void,
): Promise<UploadResponse> {
  if (USE_MOCK) {
    const results: UploadResponse['parsed'] = [];
    for (let index = 0; index < files.length; index += 1) {
      await delay(250);
      const mock = MOCK_EVIDENCE[index % MOCK_EVIDENCE.length];
      const parsed = { ...mock, filename: files[index].name, evidence_id: `ev-mock-${index}` };
      results.push(parsed);
      onProgress?.(parsed);
    }
    return {
      case_id: caseId,
      parsed: results,
      video_pending: [],
      total_evidence: results.length,
      total_entities: results.reduce((total, item) => total + item.entity_count, 0),
    };
  }

  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }

  const payload = adaptUploadResponse(
    await fetchJson<unknown>(`/cases/${caseId}/upload`, {
      method: 'POST',
      body: form,
    }),
  );

  for (const parsed of payload.parsed) {
    if (parsed.status === 'parsed' && parsed.evidence_id) {
      onProgress?.(parsed);
    }
  }

  return payload;
}

export async function analyzeCase(caseId: string): Promise<AnalysisResponse> {
  if (USE_MOCK) {
    await delay(400);
    return MOCK_ANALYSIS;
  }

  return adaptAnalysisResponse(
    await fetchJson<unknown>(`/cases/${caseId}/analyze`, {
      method: 'POST',
    }),
  );
}

export async function generateReport(caseId: string): Promise<GenerateResponse> {
  if (USE_MOCK) {
    await delay(150);
    return {
      case_id: caseId,
      job_id: 'mock-report-job',
      report_id: 'mock-report',
      status: 'queued',
      status_url: '/api/report-jobs/mock-report-job',
      stream_url: '/api/report-jobs/mock-report-job/stream',
      report_url: '/api/reports/mock-report',
    };
  }

  return adaptGenerateResponse(
    caseId,
    await fetchJson<GenerateReportJobAcceptedResponse>(`/cases/${caseId}/report-jobs`, {
      method: 'POST',
    }),
  );
}

export function streamReport(
  jobId: string,
  onInvalidate: () => void,
  onError?: (error: Error) => void,
): () => void {
  if (USE_MOCK) {
    let cancelled = false;

    (async () => {
      for (let index = 0; index < MOCK_REPORT_SECTIONS.length; index += 1) {
        if (cancelled) {
          return;
        }
        await delay(150);
        onInvalidate();
      }
    })().catch((error) => {
      if (!cancelled) {
        onError?.(error instanceof Error ? error : new Error('Mock stream failed.'));
      }
    });

    return () => {
      cancelled = true;
    };
  }

  const source = new EventSource(`${API_BASE}/report-jobs/${jobId}/stream`);
  const handleInvalidate = () => {
    onInvalidate();
  };
  const handleTerminal = () => {
    onInvalidate();
    source.close();
  };

  for (const eventName of REPORT_STREAM_EVENTS) {
    source.addEventListener(eventName, handleInvalidate);
  }
  for (const eventName of REPORT_STREAM_TERMINAL_EVENTS) {
    source.addEventListener(eventName, handleTerminal);
  }

  source.onmessage = handleInvalidate;
  source.onerror = () => {
    onError?.(new Error('Report stream connection failed.'));
    source.close();
  };

  return () => {
    for (const eventName of REPORT_STREAM_EVENTS) {
      source.removeEventListener(eventName, handleInvalidate);
    }
    for (const eventName of REPORT_STREAM_TERMINAL_EVENTS) {
      source.removeEventListener(eventName, handleTerminal);
    }
    source.close();
  };
}

export async function getCase(caseId: string): Promise<FullCase> {
  if (USE_MOCK) {
    await delay(120);
    return {
      ...MOCK_FULL_CASE,
      case_id: caseId,
      title: MOCK_CASE_TITLE,
      latest_report_id: 'mock-report',
      latest_report_job_id: 'mock-report-job',
      status: 'complete',
    };
  }

  return adaptCaseResponse(await fetchJson<unknown>(`/cases/${caseId}`));
}

export async function getCaseReport(caseId: string): Promise<CaseReportState> {
  if (USE_MOCK) {
    await delay(120);
    return buildMockCaseReportState(caseId);
  }

  return adaptCaseReportState(
    await fetchJson<unknown>(`/cases/${caseId}/report`),
  );
}

export async function getReportJob(jobId: string): Promise<ReportJobSnapshot> {
  if (USE_MOCK) {
    await delay(120);
    const mock = buildMockCaseReportState(MOCK_CASE_ID);
    return {
      job_id: jobId,
      report_id: mock.report_id ?? 'mock-report',
      status: mock.status,
      progress: mock.progress,
      warnings: mock.warnings,
      error: mock.error,
      report_sections: mock.report_sections,
      activity: mock.activity,
    };
  }

  return adaptReportJobSnapshot(
    await fetchJson<ReportGenerationJobStatusResponse>(`/report-jobs/${jobId}`),
  );
}

export async function getReport(reportId: string): Promise<ReportSection[]> {
  if (USE_MOCK) {
    await delay(120);
    return MOCK_REPORT_SECTIONS.map((section) => ({ ...section, report_id: reportId }));
  }

  const report = await fetchJson<ReportDocument>(`/reports/${reportId}`);
  return adaptReportSections(report);
}

export async function getEntityDetail(
  caseId: string,
  entityName: string,
): Promise<EntityDetailResponse> {
  if (USE_MOCK) {
    await delay(120);
    const entry = Object.values(MOCK_ENTITY_DETAILS).find(
      (detail) => detail.entity.name.toLowerCase() === entityName.toLowerCase(),
    );
    return (
      entry ?? {
        entity: { id: 'ent-unknown', type: 'person', name: entityName },
        mentions: [],
        facts: [],
        contradictions: [],
      }
    );
  }

  return adaptEntityDetailResponse(
    await fetchJson<unknown>(
      `/cases/${caseId}/entities/${encodeURIComponent(entityName)}`,
    ),
  );
}

export async function editSection(input: {
  caseId: string;
  sectionId: string;
  instruction: string;
  canonicalBlockId?: string;
  editTarget?: 'title' | 'content';
}): Promise<EditSectionResponse> {
  if (USE_MOCK) {
    await delay(250);
    return {
      case_id: input.caseId,
      report_id: 'mock-report',
      section_id: input.sectionId,
      canonical_block_id: input.canonicalBlockId ?? input.sectionId,
      status: 'updated',
      report_sections: MOCK_REPORT_SECTIONS,
    };
  }

  const payload = await fetchJson<{
    case_id: string;
    report_id: string;
    section_id: string;
    canonical_block_id: string;
    status: string;
    report: ReportDocument;
  }>('/edit/section', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      case_id: input.caseId,
      section_id: input.sectionId,
      instruction: input.instruction,
      canonical_block_id: input.canonicalBlockId,
      edit_target: input.editTarget,
    }),
  });

  return {
    case_id: payload.case_id,
    report_id: payload.report_id,
    section_id: payload.section_id,
    canonical_block_id: payload.canonical_block_id,
    status: payload.status,
    report_sections: adaptReportSections(payload.report),
  };
}
