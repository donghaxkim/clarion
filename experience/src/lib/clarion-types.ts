export type ReportBlockType = 'text' | 'image' | 'video';
export type ReportProvenance = 'evidence' | 'public_context';
export type ReportBlockState = 'pending' | 'ready' | 'failed';
export type ReportStatus = 'running' | 'completed' | 'failed';
export type ReportGenerationJobStatus =
  | 'queued'
  | 'planning'
  | 'composing'
  | 'generating_media'
  | 'completed'
  | 'failed';

export interface Citation {
  source_id: string;
  source_label?: string | null;
  excerpt?: string | null;
  segment_id?: string | null;
  page_number?: number | null;
  time_range_ms?: [number, number] | null;
  snippet?: string | null;
  uri?: string | null;
  provenance: ReportProvenance;
}

export interface MediaAsset {
  kind: 'image' | 'video';
  uri: string;
  generator: string;
  manifest_uri?: string | null;
  state: ReportBlockState;
}

export interface ReportBlock {
  id: string;
  type: ReportBlockType;
  title?: string | null;
  content?: string | null;
  sort_key: string;
  provenance: ReportProvenance;
  confidence_score: number;
  citations: Citation[];
  media: MediaAsset[];
  state: ReportBlockState;
}

export interface ReportDocument {
  report_id: string;
  status: ReportStatus;
  sections: ReportBlock[];
  warnings: string[];
  generated_at?: string | null;
}

export interface ReportGenerationActivity {
  phase: string;
  status: string;
  label: string;
  detail?: string | null;
  node_id?: string | null;
  active_node_ids: string[];
  attempt?: number | null;
  max_attempts?: number | null;
  updated_at: string;
}

export interface ReportGenerationJobStatusResponse {
  job_id: string;
  report_id: string;
  status: ReportGenerationJobStatus;
  progress: number;
  warnings: string[];
  error?: string | null;
  report?: ReportDocument | null;
  activity?: ReportGenerationActivity | null;
}

export interface GenerateReportJobAcceptedResponse {
  job_id: string;
  report_id: string;
  status_url: string;
  stream_url: string;
  report_url: string;
}
