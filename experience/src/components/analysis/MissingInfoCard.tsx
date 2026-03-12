'use client';

import React from 'react';
import { MissingInfo } from '@/lib/types';
import { SeverityBadge } from '@/components/ui/SeverityBadge';

interface MissingInfoCardProps {
  item: MissingInfo;
}

export function MissingInfoCard({ item }: MissingInfoCardProps) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '14px 16px',
        marginBottom: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '8px' }}>
        <SeverityBadge severity={item.severity} compact />
        <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4, flex: 1 }}>
          {item.description}
        </p>
      </div>
      <p
        style={{
          fontSize: '12px',
          color: 'var(--text-secondary)',
          fontStyle: 'italic',
          lineHeight: 1.5,
          paddingLeft: '0',
        }}
      >
        {item.recommendation}
      </p>
    </div>
  );
}
