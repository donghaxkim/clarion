// ─── Thumbnail & Visual Utilities ─────────────────────────────────────────────

import { EvidenceType } from '@/lib/types';

/** Returns the CSS variable value for an evidence type's color */
export function getEvidenceColor(type: EvidenceType | string): string {
  const map: Record<string, string> = {
    police_report: 'var(--evidence-police)',
    medical_record: 'var(--evidence-medical)',
    witness_statement: 'var(--evidence-witness)',
    photo: 'var(--evidence-photo)',
    video: 'var(--evidence-video)',
    audio: 'var(--evidence-audio)',
    legal_document: 'var(--evidence-police)',
    other: 'var(--evidence-other)',
  };
  return map[type] ?? 'var(--evidence-other)';
}

/** Returns a hex color for an evidence type (for SVG elements) */
export function getEvidenceHex(type: EvidenceType | string): string {
  const map: Record<string, string> = {
    police_report: '#4A6FA5',
    medical_record: '#6B9B7E',
    witness_statement: '#9B6B9B',
    photo: '#C98A2E',
    video: '#C44B4B',
    audio: '#6B6FA5',
    legal_document: '#4A6FA5',
    other: '#9C9890',
  };
  return map[type] ?? '#9C9890';
}

/** Returns a short uppercase label for the evidence type */
export function getEvidenceLabel(type: EvidenceType | string): string {
  const map: Record<string, string> = {
    police_report: 'POLICE REPORT',
    medical_record: 'MEDICAL RECORD',
    witness_statement: 'WITNESS STATEMENT',
    photo: 'PHOTO',
    video: 'VIDEO',
    audio: 'AUDIO',
    legal_document: 'LEGAL DOCUMENT',
    other: 'OTHER',
  };
  return map[type] ?? type.toUpperCase().replace('_', ' ');
}

/** Returns a light background tint for the thumbnail area */
export function getEvidenceThumbnailBg(type: EvidenceType | string): string {
  const map: Record<string, string> = {
    police_report: 'rgba(74,111,165,0.06)',
    medical_record: 'rgba(107,155,126,0.06)',
    witness_statement: 'rgba(155,107,155,0.06)',
    photo: 'rgba(201,138,46,0.06)',
    video: 'rgba(196,75,75,0.06)',
    audio: 'rgba(107,111,165,0.06)',
    legal_document: 'rgba(74,111,165,0.06)',
    other: 'rgba(156,152,144,0.06)',
  };
  return map[type] ?? 'rgba(156,152,144,0.06)';
}

/** Generate pseudo-random waveform heights for audio visualization */
export function getAudioWaveformBars(
  filename: string,
  count = 24
): number[] {
  // Deterministic but varied per filename
  const seed = filename.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return Array.from({ length: count }, (_, i) => {
    const v = Math.abs(Math.sin((seed + i * 37) * 0.5) * 0.6 + Math.sin((seed + i * 13) * 0.8) * 0.4);
    return 0.2 + v * 0.8;
  });
}

/** Check if a filename is an image type */
export function isImageFile(filename: string): boolean {
  return /\.(jpg|jpeg|png|gif|webp|bmp|svg)$/i.test(filename);
}

/** Check if a filename is an audio type */
export function isAudioFile(filename: string): boolean {
  return /\.(mp3|m4a|wav|ogg|aac|flac)$/i.test(filename);
}

/** Check if a filename is a video type */
export function isVideoFile(filename: string): boolean {
  return /\.(mp4|mov|avi|mkv|webm|wmv)$/i.test(filename);
}

/** Check if a filename is a PDF */
export function isPdfFile(filename: string): boolean {
  return /\.pdf$/i.test(filename);
}

/** Get entity type color */
export function getEntityTypeColor(type: string): string {
  const map: Record<string, string> = {
    person: '#4A6FA5',
    vehicle: '#C98A2E',
    location: '#6B9B7E',
    organization: '#9B6B9B',
    date: '#C44B4B',
    other: '#9C9890',
  };
  return map[type] ?? '#9C9890';
}
