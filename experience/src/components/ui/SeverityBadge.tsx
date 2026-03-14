'use client';

import React from 'react';
import { Severity } from '@/lib/types';

interface SeverityBadgeProps {
  severity: Severity;
  compact?: boolean;
}

const config: Record<Severity, { label: string; color: string; bg: string }> = {
  high:   { label: 'HIGH',   color: 'var(--severity-high)', bg: 'var(--severity-high-bg)' },
  medium: { label: 'MEDIUM', color: 'var(--severity-med)',  bg: 'var(--severity-med-bg)'  },
  low:    { label: 'LOW',    color: 'var(--severity-low)',  bg: 'var(--severity-low-bg)'  },
};

export function SeverityBadge({ severity, compact = false }: SeverityBadgeProps) {
  const { label, color, bg } = config[severity];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: compact ? '1px 6px' : '2px 8px',
        background: bg,
        borderLeft: `3px solid ${color}`,
        color,
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.06em',
        borderRadius: '0 3px 3px 0',
        fontFamily: 'DM Sans, sans-serif',
      }}
    >
      {label}
    </span>
  );
}
