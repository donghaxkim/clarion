// Types matching backend API schema

export interface CaseCreateResponse {
  case_id: string;
  status: string;
}

export interface ParsedEvidence {
  evidence_id: string;
  filename: string;
  evidence_type: string;
  labels: string[];
  summary: string;
  entities: string[];
  status: string;
}

export interface UploadResponse {
  case_id: string;
  parsed: ParsedEvidence[];
  video_pending: string[];
  total_evidence: number;
  total_entities: number;
}

export interface ContradictionSource {
  evidence_id: string;
  detail: string;
  excerpt: string;
}

export interface ContradictionItem {
  id: string;
  severity: "low" | "medium" | "high";
  description: string;
  fact_a: string;
  fact_b: string;
  source_a: ContradictionSource;
  source_b: ContradictionSource;
}

export interface MissingInfoItem {
  id: string;
  severity: "suggestion" | "warning" | "critical";
  description: string;
  recommendation: string;
}

export interface EntityItem {
  name: string;
  type: string;
  aliases?: string[];
}

export interface AnalyzeResponse {
  case_id: string;
  case_type_detected: string;
  dimensions_discovered: string[];
  total_facts_indexed: number;
  entities: EntityItem[];
  contradictions: {
    summary: string;
    items: ContradictionItem[];
  };
  missing_info: {
    total: number;
    critical: number;
    items: MissingInfoItem[];
  };
}

export interface GenerateResponse {
  case_id: string;
  status: string;
  stream_url: string;
}

export type BlockType =
  | "heading"
  | "text"
  | "image"
  | "evidence_image"
  | "video"
  | "timeline"
  | "diagram"
  | "counter_argument";

export interface TimelineEvent {
  id: string;
  timestamp: string;
  label: string;
  description?: string;
  section_id?: string;
}

export interface Annotation {
  x: number;
  y: number;
  label: string;
}

export interface ReportSection {
  section_id: string;
  block_type: BlockType;
  heading_level?: number;
  content: string;
  citation_ids?: string[];
  contradiction_ids?: string[];
  isStreaming?: boolean;
  annotations?: Annotation[];
  events?: TimelineEvent[];
  image_url?: string;
}

export interface Citation {
  id: string;
  evidence_id: string;
  filename: string;
  page?: number;
  timestamp?: string;
  excerpt: string;
}

export interface EntityFact {
  claim: string;
  dimension: string;
  source_filename: string;
  reliability: number;
}

export interface EntityDetail {
  name: string;
  type: string;
  aliases?: string[];
  facts: EntityFact[];
  contradictions: ContradictionItem[];
  deposition_questions?: string[];
}

export interface StreamEventData {
  event: "section_start" | "section_delta" | "section_complete" | "done";
  section_id?: string;
  block_type?: BlockType;
  heading_level?: number;
  delta?: string;
  content?: string;
  citation_ids?: string[];
  contradiction_ids?: string[];
  annotations?: Annotation[];
  events?: TimelineEvent[];
  image_url?: string;
}
