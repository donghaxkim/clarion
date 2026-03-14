// ─── Evidence ─────────────────────────────────────────────────────────────────

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
}

export interface VideoPending {
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

// ─── Case ──────────────────────────────────────────────────────────────────────

export interface CreateCaseResponse {
  case_id: string;
  status: string;
  created_at: string;
}

// ─── Analysis ─────────────────────────────────────────────────────────────────

export interface Dimension {
  name: string;
  description: string;
  importance: 'high' | 'medium' | 'low';
}

export type Severity = 'high' | 'medium' | 'low';

export interface Contradiction {
  id: string;
  severity: Severity;
  description: string;
  fact_a: { text: string; source: string; evidence_id: string };
  fact_b: { text: string; source: string; evidence_id: string };
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

// ─── Report / Streaming ────────────────────────────────────────────────────────

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
  source: string;
  page?: number;
  time?: string;
  excerpt: string;
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
}

export type StreamEvent =
  | { event: 'section_start'; section: ReportSection }
  | { event: 'section_delta'; section_id: string; delta_text: string }
  | { event: 'section_complete'; section_id: string }
  | { event: 'intelligence'; contradiction?: Contradiction; missing?: MissingInfo }
  | { event: 'status'; status: string; progress: number; message: string }
  | { event: 'done' };

export interface GenerateResponse {
  case_id: string;
  status: string;
  stream_url: string;
}

// ─── Full Case ─────────────────────────────────────────────────────────────────

export interface FullCase {
  case_id: string;
  title?: string;
  case_type?: string;
  evidence: ParsedEvidence[];
  entities: Entity[];
  contradictions: Contradiction[];
  missing_info: MissingInfo[];
  report_sections: ReportSection[];
}

// ─── Entity Deep-Dive ──────────────────────────────────────────────────────────

export interface EntityFact {
  fact: string;
  dimension: string;
  evidence_id: string;
  excerpt: string;
  reliability: number;
}

export interface EntityDetailResponse {
  entity: Entity;
  facts: EntityFact[];
  contradictions: Contradiction[];
}

// ─── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  content: string;
  timestamp: Date;
}
