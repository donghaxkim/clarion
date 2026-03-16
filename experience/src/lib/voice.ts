export type VoiceOrbState =
  | 'disconnected'
  | 'connecting'
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'awaiting_confirm'
  | 'error';

export interface VoiceSessionConfig {
  websocket_base_url: string;
}

export interface VoiceNavigateEvent {
  type: 'navigate';
  target: 'section' | 'entity' | 'evidence';
  id: string;
}

export interface VoiceEditProposalEvent {
  type: 'edit_proposal';
  section_id: string;
  canonical_block_id?: string;
  edit_target?: 'title' | 'content';
  title: string;
  instruction: string;
  summary: string;
}

export interface VoiceStatusEvent {
  type: 'state';
  value: Exclude<VoiceOrbState, 'awaiting_confirm'>;
}

export interface VoiceAudioChunkEvent {
  type: 'audio_chunk';
  data: string;
  mime_type?: string;
}

export interface VoiceAudioEndEvent {
  type: 'audio_end';
}

export interface VoiceErrorEvent {
  type: 'error';
  message: string;
}

export interface VoiceEditStatusEvent {
  type: 'edit_applied' | 'edit_cancelled';
  section_id: string;
  status?: string;
}

export type VoiceServerEvent =
  | VoiceStatusEvent
  | VoiceAudioChunkEvent
  | VoiceAudioEndEvent
  | VoiceNavigateEvent
  | VoiceEditProposalEvent
  | VoiceErrorEvent
  | VoiceEditStatusEvent;
