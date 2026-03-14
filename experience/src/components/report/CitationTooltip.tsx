'use client';

import React, { useState, useRef } from 'react';
import { Citation } from '@/lib/types';

interface CitationTooltipProps {
  citation: Citation;
  index: number;
}

export function CitationTooltip({ citation, index }: CitationTooltipProps) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  return (
    <span style={{ position: 'relative', display: 'inline' }}>
      <sup
        ref={ref}
        className="citation-ref"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
      >
        [{index + 1}]
      </sup>

      {visible && (
        <span
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginBottom: '6px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '10px 12px',
            width: '260px',
            zIndex: 20,
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            pointerEvents: 'none',
          }}
        >
          <span
            style={{
              display: 'block',
              fontSize: '11px',
              fontWeight: 500,
              color: 'var(--text-primary)',
              marginBottom: '4px',
              fontFamily: 'DM Mono, monospace',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {citation.source}
            {citation.page && ` · p. ${citation.page}`}
            {citation.time && ` · ${citation.time}`}
          </span>
          <span
            style={{
              display: 'block',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              fontStyle: 'italic',
              lineHeight: 1.4,
            }}
          >
            "{citation.excerpt}"
          </span>
        </span>
      )}
    </span>
  );
}
