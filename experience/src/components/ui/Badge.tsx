'use client';

import React from 'react';
import { EvidenceType } from '@/lib/types';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'evidence' | 'entity';
  evidenceType?: EvidenceType;
  className?: string;
}

const evidenceColors: Record<EvidenceType, string> = {
  police_report: 'var(--evidence-police)',
  medical_record: 'var(--evidence-medical)',
  witness_statement: 'var(--evidence-witness)',
  photo: 'var(--evidence-photo)',
  video: 'var(--evidence-video)',
  audio: 'var(--evidence-audio)',
  legal_document: 'var(--evidence-police)',
  other: 'var(--evidence-other)',
};

const evidenceLabels: Record<EvidenceType, string> = {
  police_report: 'POLICE REPORT',
  medical_record: 'MEDICAL RECORD',
  witness_statement: 'WITNESS STATEMENT',
  photo: 'PHOTOGRAPH',
  video: 'VIDEO',
  audio: 'AUDIO STATEMENT',
  legal_document: 'LEGAL DOCUMENT',
  other: 'DOCUMENT',
};

export function EvidenceTypeBadge({ type }: { type: EvidenceType }) {
  const color = evidenceColors[type] || 'var(--evidence-other)';
  const label = evidenceLabels[type] || 'DOCUMENT';
  return (
    <span
      style={{
        color,
        fontSize: '11px',
        fontWeight: 500,
        letterSpacing: '0.06em',
        fontFamily: 'DM Sans, sans-serif',
      }}
    >
      {label}
    </span>
  );
}

export function getEvidenceColor(type: EvidenceType): string {
  return evidenceColors[type] || 'var(--evidence-other)';
}

export function getEvidenceLabel(type: EvidenceType): string {
  return evidenceLabels[type] || 'DOCUMENT';
}

interface InlineTagProps {
  children: React.ReactNode;
  className?: string;
}

export function InlineTag({ children, className = '' }: InlineTagProps) {
  return (
    <span
      className={className}
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: '3px',
        fontSize: '11px',
        color: 'var(--text-secondary)',
        fontWeight: 400,
        lineHeight: '1.6',
      }}
    >
      {children}
    </span>
  );
}

export function EntityTypeDot({ type }: { type: string }) {
  const colors: Record<string, string> = {
    person: '#4A6FA5',
    vehicle: 'var(--accent)',
    location: 'var(--evidence-medical)',
    organization: 'var(--evidence-witness)',
    date: 'var(--text-tertiary)',
    other: 'var(--text-tertiary)',
  };
  return (
    <span
      style={{
        display: 'inline-block',
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        background: colors[type] || colors.other,
        flexShrink: 0,
      }}
    />
  );
}
