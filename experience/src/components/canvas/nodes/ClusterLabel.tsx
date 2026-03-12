'use client';

import React, { memo } from 'react';
import { NodeProps, Node } from '@xyflow/react';

export interface ClusterLabelData {
  label: string;
  [key: string]: unknown;
}

export type ClusterLabelNodeType = Node<ClusterLabelData, 'clusterLabel'>;

function ClusterLabelComponent({ data }: NodeProps<ClusterLabelNodeType>) {
  return (
    <div
      style={{
        fontFamily: 'DM Sans, sans-serif',
        fontSize: '11px',
        fontWeight: 500,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--text-tertiary)',
        pointerEvents: 'none',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        padding: '0 4px',
        animation: 'clusterLabelFadeIn 0.4s ease-out forwards',
      }}
    >
      <style>{`
        @keyframes clusterLabelFadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      {data.label}
    </div>
  );
}

export const ClusterLabel = memo(ClusterLabelComponent);
