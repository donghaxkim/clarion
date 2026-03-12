'use client';

import React, { memo, useState } from 'react';
import { NodeProps, Node } from '@xyflow/react';

export interface ClusterLabelData {
  label: string;
  childIds?: string[];
  [key: string]: unknown;
}

export type ClusterLabelNodeType = Node<ClusterLabelData, 'clusterLabel'>;

function ClusterLabelComponent({ data }: NodeProps<ClusterLabelNodeType>) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        fontFamily: 'DM Sans, sans-serif',
        fontSize: '11px',
        fontWeight: 500,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--text-tertiary)',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        padding: '2px 4px',
        cursor: 'grab',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        animation: 'clusterLabelFadeIn 0.4s ease-out forwards',
      }}
    >
      <style>{`
        @keyframes clusterLabelFadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      {/* Grip handle — visible on hover */}
      <svg
        width="12"
        height="12"
        viewBox="0 0 12 12"
        fill="none"
        style={{
          opacity: hovered ? 0.6 : 0,
          transition: 'opacity 0.15s ease',
          flexShrink: 0,
        }}
      >
        <circle cx="4" cy="3" r="1" fill="var(--text-tertiary)" />
        <circle cx="8" cy="3" r="1" fill="var(--text-tertiary)" />
        <circle cx="4" cy="6" r="1" fill="var(--text-tertiary)" />
        <circle cx="8" cy="6" r="1" fill="var(--text-tertiary)" />
        <circle cx="4" cy="9" r="1" fill="var(--text-tertiary)" />
        <circle cx="8" cy="9" r="1" fill="var(--text-tertiary)" />
      </svg>
      {data.label}
    </div>
  );
}

export const ClusterLabel = memo(ClusterLabelComponent);
