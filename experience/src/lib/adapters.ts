import type {
  GenerateReportJobAcceptedResponse,
  ReportBlock,
  ReportDocument,
  ReportGenerationJobStatusResponse,
} from '@/lib/clarion-types';
import type {
  AnalysisResponse,
  CaseReportState,
  Contradiction,
  Entity,
  EntityDetailResponse,
  EvidenceType,
  FullCase,
  GenerateResponse,
  MissingInfo,
  ParsedEvidence,
  ReportJobSnapshot,
  ReportSection,
  UploadResponse,
} from '@/lib/types';

export function adaptGenerateResponse(
  caseId: string,
  payload: GenerateReportJobAcceptedResponse,
): GenerateResponse {
  return {
    case_id: caseId,
    job_id: payload.job_id,
    report_id: payload.report_id,
    status: 'queued',
    status_url: payload.status_url,
    stream_url: payload.stream_url,
    report_url: payload.report_url,
  };
}

export function adaptUploadResponse(payload: any): UploadResponse {
  return {
    case_id: String(payload.case_id),
    parsed: Array.isArray(payload.parsed)
      ? payload.parsed.map(adaptParsedEvidence)
      : [],
    video_pending: Array.isArray(payload.video_pending)
      ? payload.video_pending.map((item: any) => ({
          evidence_id: item.evidence_id ? String(item.evidence_id) : undefined,
          filename: String(item.filename ?? 'unknown'),
          status: String(item.status ?? 'pending'),
        }))
      : [],
    total_evidence: Number(payload.total_evidence ?? 0),
    total_entities: Number(payload.total_entities ?? 0),
  };
}

export function adaptAnalysisResponse(payload: any): AnalysisResponse {
  return {
    case_id: String(payload.case_id),
    case_type_detected: String(payload.case_type_detected ?? 'Unknown case'),
    dimensions_discovered: Array.isArray(payload.dimensions_discovered)
      ? payload.dimensions_discovered.map((item: any) => ({
          name: String(item.name),
          description: String(item.description ?? ''),
          importance: normalizeSeverity(item.importance),
        }))
      : [],
    total_facts_indexed: Number(payload.total_facts_indexed ?? 0),
    total_entities: Number(payload.total_entities ?? 0),
    entities: Array.isArray(payload.entities)
      ? payload.entities.map(adaptEntity)
      : [],
    contradictions: {
      summary: {
        total: Number(payload.contradictions?.summary?.total ?? 0),
        high: Number(payload.contradictions?.summary?.high ?? 0),
        medium: Number(payload.contradictions?.summary?.medium ?? 0),
        low: Number(payload.contradictions?.summary?.low ?? 0),
      },
      items: Array.isArray(payload.contradictions?.items)
        ? payload.contradictions.items.map(adaptContradiction)
        : [],
    },
    missing_info: {
      total: Number(payload.missing_info?.total ?? 0),
      critical: Number(payload.missing_info?.critical ?? 0),
      items: Array.isArray(payload.missing_info?.items)
        ? payload.missing_info.items.map(adaptMissingInfo)
        : [],
    },
  };
}

export function adaptCaseResponse(payload: any): FullCase {
  return {
    case_id: String(payload.case_id),
    title: payload.title ? String(payload.title) : undefined,
    case_type: payload.case_type ? String(payload.case_type) : undefined,
    status: payload.status ? String(payload.status) : undefined,
    analysis_status: payload.analysis_status
      ? String(payload.analysis_status) as FullCase['analysis_status']
      : undefined,
    analysis_error: payload.analysis_error ? String(payload.analysis_error) : null,
    analysis_updated_at: payload.analysis_updated_at
      ? String(payload.analysis_updated_at)
      : null,
    evidence_revision: Number(payload.evidence_revision ?? 0),
    analysis_revision: Number(payload.analysis_revision ?? 0),
    latest_report_id: payload.latest_report_id ? String(payload.latest_report_id) : null,
    latest_report_job_id: payload.latest_report_job_id
      ? String(payload.latest_report_job_id)
      : null,
    evidence: Array.isArray(payload.evidence)
      ? payload.evidence.map(adaptParsedEvidence)
      : [],
    entities: Array.isArray(payload.entities)
      ? payload.entities.map(adaptEntity)
      : [],
    report_relevant_entities: Array.isArray(payload.report_relevant_entities)
      ? payload.report_relevant_entities.map(adaptEntity)
      : [],
    contradictions: Array.isArray(payload.contradictions)
      ? payload.contradictions.map(adaptContradiction)
      : [],
    missing_info: Array.isArray(payload.missing_info)
      ? payload.missing_info.map(adaptMissingInfo)
      : [],
    report_sections: Array.isArray(payload.report_sections)
      ? payload.report_sections
      : [],
  };
}

export function adaptEntityDetailResponse(payload: any): EntityDetailResponse {
  return {
    entity: adaptEntity(payload.entity ?? {}),
    mentions: Array.isArray(payload.mentions)
      ? payload.mentions.map((item: any) => ({
          evidence_id: String(item.evidence_id ?? ''),
          source: String(item.source ?? item.evidence_id ?? ''),
          page: typeof item.page === 'number' ? item.page : undefined,
          timestamp_start:
            typeof item.timestamp_start === 'number' ? item.timestamp_start : null,
          excerpt: String(item.excerpt ?? ''),
        }))
      : [],
    facts: Array.isArray(payload.facts)
      ? payload.facts.map((item: any) => ({
          fact: String(item.fact ?? ''),
          dimension: String(item.dimension ?? ''),
          source: String(item.source ?? item.evidence_id ?? ''),
          evidence_id: String(item.evidence_id ?? item.source_evidence_id ?? ''),
          page: typeof item.page === 'number' ? item.page : undefined,
          timestamp_start:
            typeof item.timestamp_start === 'number' ? item.timestamp_start : null,
          excerpt: String(item.excerpt ?? ''),
          reliability: Number(item.reliability ?? 0),
        }))
      : [],
    contradictions: Array.isArray(payload.contradictions)
      ? payload.contradictions.map(adaptContradiction)
      : [],
  };
}

export function adaptReportJobSnapshot(
  payload: ReportGenerationJobStatusResponse,
): ReportJobSnapshot {
  return {
    job_id: payload.job_id,
    report_id: payload.report_id,
    status: payload.status,
    progress: payload.progress,
    warnings: payload.warnings ?? [],
    error: payload.error ?? null,
    report_sections: adaptReportSections(payload.report ?? null),
    activity: payload.activity
      ? {
          phase: payload.activity.phase,
          status: payload.activity.status,
          label: payload.activity.label,
          detail: payload.activity.detail ?? null,
        }
      : null,
  };
}

export function adaptCaseReportState(payload: any): CaseReportState {
  const reportJobPayload = payload as ReportGenerationJobStatusResponse;
  return {
    case_id: String(payload.case_id),
    job_id: reportJobPayload.job_id ? String(reportJobPayload.job_id) : null,
    report_id: reportJobPayload.report_id ? String(reportJobPayload.report_id) : null,
    status: String(reportJobPayload.status ?? 'queued'),
    progress: Number(reportJobPayload.progress ?? 0),
    warnings: reportJobPayload.warnings ?? [],
    error: reportJobPayload.error ?? null,
    report_sections: adaptReportSections(reportJobPayload.report ?? null),
    activity: reportJobPayload.activity
      ? {
          phase: reportJobPayload.activity.phase,
          status: reportJobPayload.activity.status,
          label: reportJobPayload.activity.label,
          detail: reportJobPayload.activity.detail ?? null,
        }
      : null,
  };
}

export function adaptReportSections(report: ReportDocument | null | undefined): ReportSection[] {
  if (!report) {
    return [];
  }

  const orderedBlocks = [...report.sections].sort((left, right) =>
    left.sort_key.localeCompare(right.sort_key),
  );

  const sections: ReportSection[] = [];
  let order = 0;

  for (const block of orderedBlocks) {
    if (block.title) {
      sections.push({
        id: `${block.id}--heading`,
        block_type: 'heading',
        order: order++,
        text: block.title,
        heading_level: 2,
        canonical_block_id: block.id,
        edit_target: 'title',
        report_id: report.report_id,
      });
    }

    const citations = block.citations.map((citation, index) => adaptCitation(citation, index));
    const primaryMedia = getPrimaryMedia(block);
    const contentText =
      block.type === 'text'
        ? appendCitationMarkers(block.content ?? '', citations.length)
        : block.content ?? block.title ?? '';

    sections.push({
      id: block.id,
      block_type: mapBlockType(block),
      order: order++,
      text: contentText || undefined,
      media: primaryMedia?.uri,
      citations,
      canonical_block_id: block.id,
      edit_target:
        block.type === 'text'
          ? 'content'
          : block.title
            ? 'title'
            : 'content',
      report_id: report.report_id,
    });
  }

  return sections;
}

export function isTerminalReportStatus(status: string): boolean {
  return status === 'completed' || status === 'failed';
}

function adaptParsedEvidence(payload: any): ParsedEvidence {
  const normalizedStatus =
    payload.status === 'pending'
      ? 'pending'
      : payload.status === 'error' || payload.status === 'parse_failed'
        ? 'error'
        : 'parsed';

  return {
    evidence_id: String(payload.evidence_id ?? payload.id ?? ''),
    filename: String(payload.filename ?? 'unknown'),
    evidence_type: normalizeEvidenceType(payload.evidence_type),
    labels: Array.isArray(payload.labels) ? payload.labels.map(String) : [],
    summary: String(payload.summary ?? ''),
    entity_count: Number(payload.entity_count ?? payload.entities?.length ?? 0),
    entities: Array.isArray(payload.entities)
      ? payload.entities.map((entity: any) => ({
          type: String(entity.type ?? 'other'),
          name: String(entity.name ?? ''),
        }))
      : [],
    status: normalizedStatus,
    error: payload.error ? String(payload.error) : undefined,
  };
}

function adaptEntity(payload: any): Entity {
  return {
    id: String(payload.id ?? ''),
    type: normalizeEntityType(payload.type),
    name: String(payload.name ?? ''),
    aliases: Array.isArray(payload.aliases) ? payload.aliases.map(String) : undefined,
  };
}

function adaptContradiction(payload: any): Contradiction {
  const factA = adaptContradictionFact(payload.fact_a, payload.source_a);
  const factB = adaptContradictionFact(payload.fact_b, payload.source_b);
  return {
    id: String(payload.id ?? ''),
    severity: normalizeSeverity(payload.severity),
    description: String(payload.description ?? ''),
    fact_a: factA,
    fact_b: factB,
  };
}

function adaptContradictionFact(rawFact: any, sourcePin: any) {
  if (rawFact && typeof rawFact === 'object') {
    return {
      text: String(rawFact.text ?? ''),
      source: String(rawFact.source ?? ''),
      evidence_id: String(rawFact.evidence_id ?? ''),
    };
  }

  return {
    text: String(rawFact ?? ''),
    source: String(sourcePin?.detail ?? ''),
    evidence_id: String(sourcePin?.evidence_id ?? ''),
  };
}

function adaptMissingInfo(payload: any): MissingInfo {
  return {
    id: String(payload.id ?? ''),
    severity: normalizeSeverity(payload.severity),
    description: String(payload.description ?? ''),
    recommendation: String(payload.recommendation ?? ''),
  };
}

function adaptCitation(payload: any, index: number) {
  return {
    id: `${String(payload.source_id ?? 'citation')}-${index + 1}`,
    source_id: String(payload.source_id ?? ''),
    source_label: String(payload.source_label ?? ''),
    excerpt: String(payload.excerpt ?? ''),
    uri: payload.uri ? String(payload.uri) : null,
    evidence_id: payload.source_id ? String(payload.source_id) : undefined,
  };
}

function getPrimaryMedia(block: ReportBlock) {
  if (!Array.isArray(block.media) || block.media.length === 0) {
    return null;
  }
  return block.media[0] ?? null;
}

function appendCitationMarkers(text: string, citationCount: number): string {
  if (!text.trim() || citationCount <= 0) {
    return text;
  }
  const markers = Array.from({ length: citationCount }, (_, index) => ` [${index + 1}]`).join('');
  return `${text}${markers}`;
}

function mapBlockType(block: ReportBlock): ReportSection['block_type'] {
  if (block.type === 'image') {
    return 'image';
  }
  if (block.type === 'video') {
    return 'video';
  }
  return 'text';
}

function normalizeEvidenceType(value: unknown): EvidenceType {
  switch (String(value ?? '').toLowerCase()) {
    case 'medical':
    case 'medical_record':
      return 'medical_record';
    case 'official_record':
    case 'legal_document':
    case 'insurance_document':
      return 'legal_document';
    case 'transcript':
    case 'witness_statement':
      return 'witness_statement';
    case 'image':
    case 'photo':
      return 'photo';
    case 'video':
    case 'dashcam_video':
    case 'surveillance_video':
      return 'video';
    case 'audio':
      return 'audio';
    case 'police_report':
      return 'police_report';
    default:
      return 'other';
  }
}

function normalizeEntityType(value: unknown): Entity['type'] {
  const normalized = String(value ?? '').toLowerCase();
  if (
    normalized === 'person' ||
    normalized === 'vehicle' ||
    normalized === 'location' ||
    normalized === 'organization' ||
    normalized === 'date'
  ) {
    return normalized;
  }
  return 'other';
}

function normalizeSeverity(value: unknown): 'high' | 'medium' | 'low' {
  const normalized = String(value ?? '').toLowerCase();
  if (normalized === 'critical' || normalized === 'high') {
    return 'high';
  }
  if (normalized === 'warning' || normalized === 'medium') {
    return 'medium';
  }
  return 'low';
}
