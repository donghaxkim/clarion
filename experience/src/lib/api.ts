import {
  CreateCaseResponse,
  UploadResponse,
  AnalysisResponse,
  GenerateResponse,
  FullCase,
  EntityDetailResponse,
  StreamEvent,
  ReportSection,
} from './types';

import {
  MOCK_CASE_ID,
  MOCK_ANALYSIS,
  MOCK_EVIDENCE,
  MOCK_FULL_CASE,
  MOCK_REPORT_SECTIONS,
  MOCK_ENTITY_DETAILS,
} from './mock-data';

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Case ──────────────────────────────────────────────────────────────────────

export async function createCase(opts?: {
  title?: string;
  case_type?: string;
  description?: string;
}): Promise<CreateCaseResponse> {
  if (USE_MOCK) {
    await delay(400);
    return { case_id: MOCK_CASE_ID, status: 'created', created_at: new Date().toISOString() };
  }
  const form = new FormData();
  if (opts?.title) form.append('title', opts.title);
  if (opts?.case_type) form.append('case_type', opts.case_type);
  if (opts?.description) form.append('description', opts.description);
  const res = await fetch(`${API_BASE}/api/case/create`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Failed to create case: ${res.statusText}`);
  return res.json();
}

// ─── Upload ────────────────────────────────────────────────────────────────────

export async function uploadFiles(
  caseId: string,
  files: File[],
  onProgress?: (evidence: UploadResponse['parsed'][0]) => void
): Promise<UploadResponse> {
  if (USE_MOCK) {
    const results: UploadResponse['parsed'] = [];
    for (let i = 0; i < files.length; i++) {
      await delay(600 + Math.random() * 400);
      const mock = MOCK_EVIDENCE[i % MOCK_EVIDENCE.length];
      const ev = { ...mock, filename: files[i].name, evidence_id: `ev-mock-${i}` };
      results.push(ev);
      onProgress?.(ev);
    }
    return { case_id: caseId, parsed: results, video_pending: [], total_evidence: results.length, total_entities: 8 };
  }
  const form = new FormData();
  files.forEach((f) => form.append('files[]', f));
  const res = await fetch(`${API_BASE}/api/case/${caseId}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

// ─── Analyze ───────────────────────────────────────────────────────────────────

export async function analyzeCase(caseId: string): Promise<AnalysisResponse> {
  if (USE_MOCK) {
    await delay(1800);
    return MOCK_ANALYSIS;
  }
  const res = await fetch(`${API_BASE}/api/case/${caseId}/analyze`, { method: 'POST' });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

// ─── Generate ──────────────────────────────────────────────────────────────────

export async function generateReport(caseId: string): Promise<GenerateResponse> {
  if (USE_MOCK) {
    await delay(300);
    return { case_id: caseId, status: 'streaming', stream_url: `/api/stream/${caseId}` };
  }
  const res = await fetch(`${API_BASE}/api/case/${caseId}/generate`, { method: 'POST' });
  if (!res.ok) throw new Error(`Generate failed: ${res.statusText}`);
  return res.json();
}

// ─── Stream ────────────────────────────────────────────────────────────────────

export function streamReport(
  caseId: string,
  onEvent: (event: StreamEvent) => void,
  onError?: (err: Error) => void
): () => void {
  if (USE_MOCK) {
    let cancelled = false;

    (async () => {
      const sections = MOCK_REPORT_SECTIONS;

      for (const section of sections) {
        if (cancelled) break;

        onEvent({ event: 'section_start', section: { ...section, text: '' } });
        await delay(200);

        if (section.text) {
          const words = section.text.split(' ');
          let accumulated = '';
          for (const word of words) {
            if (cancelled) break;
            accumulated += (accumulated ? ' ' : '') + word;
            onEvent({ event: 'section_delta', section_id: section.id, delta_text: word + ' ' });
            await delay(30 + Math.random() * 40);
          }
        } else if (section.block_type === 'timeline' || section.block_type === 'heading') {
          // Non-text sections arrive complete
        }

        onEvent({ event: 'section_complete', section_id: section.id });
        await delay(150);
      }

      if (!cancelled) {
        onEvent({ event: 'status', status: 'complete', progress: 100, message: 'Report generation complete' });
        await delay(200);
        onEvent({ event: 'done' });
      }
    })();

    return () => { cancelled = true; };
  }

  const es = new EventSource(`${API_BASE}/api/stream/${caseId}`);
  es.onmessage = (e) => {
    try {
      const parsed: StreamEvent = JSON.parse(e.data);
      onEvent(parsed);
    } catch (err) {
      onError?.(new Error('Failed to parse stream event'));
    }
  };
  es.onerror = () => {
    onError?.(new Error('Stream connection failed'));
    es.close();
  };
  return () => es.close();
}

// ─── Case State ────────────────────────────────────────────────────────────────

export async function getCase(caseId: string): Promise<FullCase> {
  if (USE_MOCK) {
    await delay(300);
    return MOCK_FULL_CASE;
  }
  const res = await fetch(`${API_BASE}/api/case/${caseId}`);
  if (!res.ok) throw new Error(`Failed to fetch case: ${res.statusText}`);
  return res.json();
}

// ─── Entity Detail ─────────────────────────────────────────────────────────────

export async function getEntityDetail(caseId: string, entityName: string): Promise<EntityDetailResponse> {
  if (USE_MOCK) {
    await delay(300);
    const entry = Object.values(MOCK_ENTITY_DETAILS).find(
      (d) => d.entity.name.toLowerCase() === entityName.toLowerCase()
    );
    if (!entry) {
      return {
        entity: { id: 'ent-unknown', type: 'person', name: entityName },
        facts: [],
        contradictions: [],
      };
    }
    return entry;
  }
  const res = await fetch(`${API_BASE}/api/case/${caseId}/entities/${encodeURIComponent(entityName)}`);
  if (!res.ok) throw new Error(`Failed to fetch entity: ${res.statusText}`);
  return res.json();
}

// ─── Edit Section ──────────────────────────────────────────────────────────────

export async function editSection(
  caseId: string,
  sectionId: string,
  instruction: string
): Promise<{ case_id: string; section_id: string; status: string }> {
  if (USE_MOCK) {
    await delay(2000);
    return { case_id: caseId, section_id: sectionId, status: 'updated' };
  }
  const form = new FormData();
  form.append('section_id', sectionId);
  form.append('instruction', instruction);
  const res = await fetch(`${API_BASE}/api/case/${caseId}/edit-section`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Edit failed: ${res.statusText}`);
  return res.json();
}
