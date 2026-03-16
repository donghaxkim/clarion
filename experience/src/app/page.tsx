'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';

import type { WorkspaceSummary } from '@/components/canvas/EvidenceCanvas';

const EvidenceCanvas = dynamic(
  () => import('@/components/canvas/EvidenceCanvas').then((module) => module.EvidenceCanvas),
  { ssr: false },
);

const DEFAULT_SUMMARY: WorkspaceSummary = {
  caseId: null,
  title: 'Untitled Matter',
  statusText: 'No files indexed',
  evidenceCount: 0,
};

export default function WorkspacePage() {
  const [workspaceSummary, setWorkspaceSummary] = useState<WorkspaceSummary>(DEFAULT_SUMMARY);

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
          {workspaceSummary.title}
        </div>

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
              background: workspaceSummary.evidenceCount > 0 ? '#6B9B7E' : 'var(--border)',
              display: 'inline-block',
            }}
          />
          {workspaceSummary.statusText}
        </div>
      </header>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <EvidenceCanvas onWorkspaceChange={setWorkspaceSummary} />
      </div>
    </div>
  );
}
