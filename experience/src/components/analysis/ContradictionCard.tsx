'use client';

import React, { forwardRef } from 'react';
import { Contradiction } from '@/lib/types';
import { SeverityBadge } from '@/components/ui/SeverityBadge';

interface ContradictionCardProps {
  contradiction: Contradiction;
  index: number;
}

export const ContradictionCard = forwardRef<HTMLDivElement, ContradictionCardProps>(
  ({ contradiction, index }, ref) => {
    const severityColors = {
      high: 'var(--severity-high)',
      medium: 'var(--severity-med)',
      low: 'var(--severity-low)',
    };
    const borderColor = severityColors[contradiction.severity];

    return (
      <div
        ref={ref}
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderLeft: `3px solid ${borderColor}`,
          borderRadius: '6px',
          padding: '16px',
          marginBottom: '12px',
        }}
      >
        {/* Severity + description */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '12px' }}>
          <SeverityBadge severity={contradiction.severity} />
          <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4, flex: 1 }}>
            {contradiction.description}
          </p>
        </div>

        {/* Fact A vs Fact B */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'stretch' }}>
          <FactBox fact={contradiction.fact_a} />

          {/* VS divider */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              gap: '4px',
            }}
          >
            <div style={{ flex: 1, width: '1px', background: 'var(--border)' }} />
            <span
              style={{
                fontSize: '9px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: 'var(--text-tertiary)',
                fontFamily: 'DM Mono, monospace',
              }}
            >
              VS
            </span>
            <div style={{ flex: 1, width: '1px', background: 'var(--border)' }} />
          </div>

          <FactBox fact={contradiction.fact_b} />
        </div>
      </div>
    );
  }
);

ContradictionCard.displayName = 'ContradictionCard';

function FactBox({ fact }: { fact: { text: string; source: string; evidence_id: string } }) {
  return (
    <div
      style={{
        flex: 1,
        background: 'var(--bg-elevated)',
        borderRadius: '4px',
        padding: '10px 12px',
      }}
    >
      <p style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: '6px' }}>
        {fact.text}
      </p>
      <span
        style={{
          fontSize: '10px',
          color: 'var(--text-tertiary)',
          fontFamily: 'DM Mono, monospace',
          display: 'block',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {fact.source}
      </span>
    </div>
  );
}
