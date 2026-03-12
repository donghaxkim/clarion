'use client';

import React, { memo } from 'react';
import { NodeProps, Node } from '@xyflow/react';

export type InsightType = 'contradiction' | 'corroboration' | 'missing';

export interface InsightBadgeData {
  insightType: InsightType;
  text: string;
  [key: string]: unknown;
}

export type InsightBadgeNodeType = Node<InsightBadgeData, 'insightBadge'>;

const INSIGHT_STYLES: Record<InsightType, {
  bg: string;
  border: string;
  color: string;
  icon: string;
}> = {
  contradiction: {
    bg: 'rgba(196,75,75,0.08)',
    border: 'rgba(196,75,75,0.3)',
    color: '#C44B4B',
    icon: '⚡',
  },
  corroboration: {
    bg: 'rgba(107,155,126,0.08)',
    border: 'rgba(107,155,126,0.3)',
    color: '#6B9B7E',
    icon: '✓',
  },
  missing: {
    bg: 'rgba(201,168,76,0.08)',
    border: 'rgba(201,168,76,0.3)',
    color: '#C9A84C',
    icon: '?',
  },
};

function InsightBadgeComponent({ data }: NodeProps<InsightBadgeNodeType>) {
  const styles = INSIGHT_STYLES[data.insightType] ?? INSIGHT_STYLES.contradiction;

  return (
    <div
      style={{
        background: styles.bg,
        border: `1px solid ${styles.border}`,
        borderRadius: '6px',
        padding: '4px 8px',
        display: 'flex',
        alignItems: 'center',
        gap: '5px',
        fontFamily: 'DM Sans, sans-serif',
        fontSize: '11px',
        fontWeight: 500,
        color: styles.color,
        pointerEvents: 'none',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        animation: 'insightBadgeFadeIn 0.4s ease-out forwards',
        backdropFilter: 'blur(4px)',
      }}
    >
      <style>{`
        @keyframes insightBadgeFadeIn {
          from { opacity: 0; transform: scale(0.85) translateY(4px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
      <span style={{ fontSize: '12px' }}>{styles.icon}</span>
      {data.text}
    </div>
  );
}

export const InsightBadge = memo(InsightBadgeComponent);
