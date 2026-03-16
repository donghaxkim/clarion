export type EvidenceType =
  | 'police_report'
  | 'medical_record'
  | 'witness_statement'
  | 'photo'
  | 'video'
  | 'audio'
  | 'legal_document'
  | 'other';

export interface Entity {
  id: string;
  type: 'person' | 'vehicle' | 'location' | 'organization' | 'date' | 'other';
  name: string;
  aliases?: string[];
}

export interface ParsedEvidence {
  evidence_id: string;
  filename: string;
  evidence_type: EvidenceType;
  labels: string[];
  summary: string;
  entity_count: number;
  entities: { type: string; name: string }[];
  status: 'parsed' | 'pending' | 'error';
  error?: string;
}

export interface VideoPending {
  evidence_id?: string;
  filename: string;
  status: string;
}

export interface UploadResponse {
  case_id: string;
  parsed: ParsedEvidence[];
  video_pending: VideoPending[];
  total_evidence: number;
  total_entities: number;
}

export interface CreateCaseResponse {
  case_id: string;
  status: string;
  created_at: string;
}

export interface Dimension {
  name: string;
  description: string;
  importance: 'high' | 'medium' | 'low';
}

export type Severity = 'high' | 'medium' | 'low';

export interface ContradictionFact {
  text: string;
  source: string;
  evidence_id: string;
}

export interface Contradiction {
  id: string;
  severity: Severity;
  description: string;
  fact_a: ContradictionFact;
  fact_b: ContradictionFact;
}

export interface MissingInfo {
  id: string;
  severity: Severity;
  description: string;
  recommendation: string;
}

export interface AnalysisResponse {
  case_id: string;
  case_type_detected: string;
  dimensions_discovered: Dimension[];
  total_facts_indexed: number;
  total_entities: number;
  entities: Entity[];
  contradictions: {
    summary: { total: number; high: number; medium: number; low: number };
    items: Contradiction[];
  };
  missing_info: {
    total: number;
    critical: number;
    items: MissingInfo[];
  };
}

export type BlockType =
  | 'heading'
  | 'text'
  | 'image'
  | 'evidence_image'
  | 'timeline'
  | 'counter_argument'
  | 'video';

export interface Citation {
  id: string;
  source_id: string;
  source_label: string;
  excerpt: string;
  uri?: string | null;
  evidence_id?: string;
}

export interface TimelineEvent {
  time: string;
  label: string;
  detail?: string;
}

export interface ReportSection {
  id: string;
  block_type: BlockType;
  order: number;
  text?: string;
  heading_level?: 1 | 2 | 3;
  media?: string;
  citations?: Citation[];
  entity_ids?: string[];
  timeline_events?: TimelineEvent[];
  canonical_block_id?: string;
  edit_target?: 'title' | 'content';
  report_id?: string;
}

export interface GenerateResponse {
  case_id: string;
  job_id: string;
  report_id: string;
  status: string;
  status_url: string;
  stream_url: string;
  report_url: string;
}

export interface FullCase {
  case_id: string;
  title?: string;
  case_type?: string;
  status?: string;
  analysis_status?: 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'stale';
  analysis_error?: string | null;
  analysis_updated_at?: string | null;
  evidence_revision?: number;
  analysis_revision?: number;
  latest_report_id?: string | null;
  latest_report_job_id?: string | null;
  evidence: ParsedEvidence[];
  entities: Entity[];
  report_relevant_entities?: Entity[];
  contradictions: Contradiction[];
  missing_info: MissingInfo[];
  report_sections: ReportSection[];
}

export interface CaseReportState {
  case_id: string;
  job_id: string | null;
  report_id: string | null;
  status: string;
  progress: number;
  warnings: string[];
  error?: string | null;
  report_sections: ReportSection[];
  activity?: {
    phase: string;
    status: string;
    label: string;
    detail?: string | null;
  } | null;
}

export interface ReportJobSnapshot {
  job_id: string;
  report_id: string;
  status: string;
  progress: number;
  warnings: string[];
  error?: string | null;
  report_sections: ReportSection[];
  activity?: {
    phase: string;
    status: string;
    label: string;
    detail?: string | null;
  } | null;
}

export interface EditSectionResponse {
  case_id: string;
  report_id: string;
  section_id: string;
  canonical_block_id: string;
  status: string;
  report_sections: ReportSection[];
}

export interface EntityFact {
  fact: string;
  dimension: string;
  source?: string;
  evidence_id: string;
  page?: number;
  timestamp_start?: number | null;
  excerpt: string;
  reliability: number;
}

export interface EntityMentionDetail {
  evidence_id: string;
  source: string;
  page?: number;
  timestamp_start?: number | null;
  excerpt: string;
}

export interface EntityDetailResponse {
  entity: Entity;
  mentions: EntityMentionDetail[];
  facts: EntityFact[];
  contradictions: Contradiction[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  content: string;
  timestamp: Date;
}
