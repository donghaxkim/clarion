export type EvidenceItemType =
  | "pdf"
  | "image"
  | "audio"
  | "video"
  | "transcript"
  | "medical"
  | "official_record"
  | "other";

export type ReportBlockType = "text" | "image" | "video" | "timeline";
export type ReportProvenance = "evidence" | "public_context";
export type ReportBlockState = "pending" | "ready" | "failed";
export type ReportStatus = "running" | "completed" | "failed";
export type ReportGenerationJobStatus =
  | "queued"
  | "planning"
  | "composing"
  | "generating_media"
  | "completed"
  | "failed";
export type ReportGenerationPhase =
  | "queued"
  | "intake"
  | "timeline_planning"
  | "grounding_review"
  | "parallel_planning"
  | "composition"
  | "media_generation"
  | "finalizing";
export type ReportGenerationActivityStatus = "running" | "completed" | "failed";
export type MediaAssetKind = "image" | "video";
export type ReportPanelMode = "citations" | "edit";
export type ReportWorkflowNodeKind = "agent" | "worker";
export type ReportWorkflowLane =
  | "chronology"
  | "review"
  | "planning"
  | "composition"
  | "media"
  | "finalize";
export type ReportWorkflowEdgeRelation = "sequence" | "loop" | "parallel";
export type ReportWorkflowNodeStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export interface SourceSpan {
  segment_id?: string | null;
  page_number?: number | null;
  time_range_ms?: [number, number] | null;
  snippet?: string | null;
  uri?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  kind: EvidenceItemType;
  title?: string | null;
  summary?: string | null;
  extracted_text?: string | null;
  media_uri?: string | null;
  source_uri?: string | null;
  source_spans: SourceSpan[];
  metadata: Record<string, string | number | boolean | null>;
  confidence_score: number;
}

export interface EventCandidate {
  event_id: string;
  title: string;
  description: string;
  sort_key: string;
  timestamp_label?: string | null;
  evidence_refs: string[];
  scene_description?: string | null;
  image_prompt_hint?: string | null;
  reference_image_uris: string[];
  public_context_queries: string[];
}

export interface EntityMention {
  entity_id: string;
  name: string;
  role?: string | null;
  description?: string | null;
}

export interface CaseEvidenceBundle {
  case_id: string;
  case_summary?: string | null;
  generation_instructions?: string | null;
  evidence_items: EvidenceItem[];
  event_candidates: EventCandidate[];
  entities: EntityMention[];
}

export interface GenerateReportRequest {
  bundle: CaseEvidenceBundle;
  user_id: string;
  enable_public_context?: boolean | null;
  max_images?: number | null;
  max_reconstructions?: number | null;
}

export interface Citation {
  source_id: string;
  segment_id?: string | null;
  page_number?: number | null;
  time_range_ms?: [number, number] | null;
  snippet?: string | null;
  uri?: string | null;
  provenance: ReportProvenance;
}

export interface MediaAsset {
  kind: MediaAssetKind;
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

export interface ReportArtifactRefs {
  report_gcs_uri?: string | null;
  report_url?: string | null;
  manifest_gcs_uri?: string | null;
}

export interface ReportGenerationActivity {
  phase: ReportGenerationPhase;
  status: ReportGenerationActivityStatus;
  label: string;
  detail?: string | null;
  node_id?: string | null;
  active_node_ids: string[];
  attempt?: number | null;
  max_attempts?: number | null;
  updated_at: string;
}

export interface ReportWorkflowNode {
  node_id: string;
  label: string;
  kind: ReportWorkflowNodeKind;
  lane: ReportWorkflowLane;
  optional: boolean;
}

export interface ReportWorkflowEdge {
  source_node_id: string;
  target_node_id: string;
  relation: ReportWorkflowEdgeRelation;
}

export interface ReportWorkflowNodeState {
  node_id: string;
  status: ReportWorkflowNodeStatus;
  detail?: string | null;
  attempt?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ReportWorkflowState {
  version: string;
  nodes: ReportWorkflowNode[];
  edges: ReportWorkflowEdge[];
  node_states: ReportWorkflowNodeState[];
  active_node_ids: string[];
}

export interface ReportDocument {
  report_id: string;
  status: ReportStatus;
  sections: ReportBlock[];
  warnings: string[];
  generated_at?: string | null;
}

export interface ReportJobEvent {
  event_id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface GenerateReportJobAcceptedResponse {
  job_id: string;
  report_id: string;
  status_url: string;
  stream_url: string;
  report_url: string;
}

export interface ReportGenerationJobStatusResponse {
  job_id: string;
  report_id: string;
  status: ReportGenerationJobStatus;
  progress: number;
  warnings: string[]; 
  error?: string | null;
  report?: ReportDocument | null;
  artifacts?: ReportArtifactRefs | null;
  activity?: ReportGenerationActivity | null;
  workflow?: ReportWorkflowState | null;
}

export const reportPanelModes = ["citations", "edit"] as const;

export function isReportPanelMode(
  value: string | null | undefined,
): value is ReportPanelMode {
  return reportPanelModes.some((mode) => mode === value);
}
