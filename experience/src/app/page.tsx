'use client';

import React from 'react';
import dynamic from 'next/dynamic';

const EvidenceCanvas = dynamic(
  () => import('@/components/canvas/EvidenceCanvas').then((m) => m.EvidenceCanvas),
  { ssr: false }
);

export default function WorkspacePage() {
  return (
    <div
      style={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg)',
      }}
    >
      {/* CLARION wordmark bar */}
      <header
        style={{
          height: '48px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          background: 'var(--bg-surface)',
          flexShrink: 0,
          zIndex: 20,
        }}
      >
        <span
          style={{
            fontSize: '12px',
            fontWeight: 600,
            letterSpacing: '0.15em',
            color: 'var(--text-primary)',
            fontFamily: 'DM Sans, sans-serif',
            textTransform: 'uppercase',
          }}
        >
          Clarion
        </span>

        {/* Case title in header */}
        <div
          style={{
            marginLeft: '16px',
            paddingLeft: '16px',
            borderLeft: '1px solid var(--border)',
            fontSize: '12px',
            color: 'var(--text-tertiary)',
            fontFamily: 'DM Sans, sans-serif',
          }}
        >
          Chen v. Thompson — Rear-End Collision
        </div>

        {/* Status indicator */}
        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            color: 'var(--text-tertiary)',
            fontFamily: 'DM Mono, monospace',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: '#6B9B7E',
              display: 'inline-block',
            }}
          />
          6 files indexed
        </div>
      </header>

      {/* Canvas fills remaining height */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <EvidenceCanvas />
      </div>
    </div>
  );
}
