'use client';

import React, { useState } from 'react';
import { useReactFlow, useViewport } from '@xyflow/react';
import { Plus, Minus, Maximize2 } from 'lucide-react';

export function ZoomControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const { zoom } = useViewport();

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '24px',
        right: '20px',
        zIndex: 10,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '4px',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      <ZoomButton
        title="Zoom in"
        onClick={() => zoomIn({ duration: 200 })}
      >
        <Plus size={14} strokeWidth={2} />
      </ZoomButton>

      <div
        style={{
          fontSize: '10px',
          fontFamily: 'DM Mono, monospace',
          color: 'var(--text-tertiary)',
          textAlign: 'center',
          padding: '2px 4px',
          userSelect: 'none',
          letterSpacing: '-0.02em',
        }}
      >
        {Math.round(zoom * 100)}%
      </div>

      <ZoomButton
        title="Zoom out"
        onClick={() => zoomOut({ duration: 200 })}
      >
        <Minus size={14} strokeWidth={2} />
      </ZoomButton>

      <div style={{ height: '1px', background: 'var(--border)', margin: '2px 0' }} />

      <ZoomButton
        title="Fit view"
        onClick={() => fitView({ duration: 400, padding: 0.15 })}
      >
        <Maximize2 size={13} strokeWidth={2} />
      </ZoomButton>
    </div>
  );
}

function ZoomButton({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <button
      title={title}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '28px',
        height: '28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
        border: `1px solid ${hovered ? 'var(--accent)' : 'transparent'}`,
        borderRadius: '4px',
        cursor: 'pointer',
        color: hovered ? 'var(--accent)' : 'var(--text-secondary)',
        transition: 'border-color 0.15s, color 0.15s',
        outline: 'none',
      }}
    >
      {children}
    </button>
  );
}
