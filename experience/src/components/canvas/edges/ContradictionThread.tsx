'use client';

import React, { memo, useState } from 'react';
import {
  EdgeProps,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Edge,
} from '@xyflow/react';
import { AlertTriangle } from 'lucide-react';

export interface ContradictionThreadData {
  severity: 'high' | 'medium' | 'low';
  description: string;
  factA: string;
  factB: string;
  [key: string]: unknown;
}

export type ContradictionThreadEdge = Edge<ContradictionThreadData, 'contradictionThread'>;

const SEVERITY_COLORS = {
  high: '#C44B4B',
  medium: '#C98A2E',
  low: '#9C9890',
};

function ContradictionThreadComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<ContradictionThreadEdge>) {
  const [hovered, setHovered] = useState(false);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.3,
  });

  const severity = data?.severity ?? 'high';
  const color = SEVERITY_COLORS[severity];
  const isActive = selected || hovered;

  return (
    <>
      {/* Glow layer */}
      <BaseEdge
        id={`${id}-glow`}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: isActive ? 8 : 6,
          opacity: 0.08,
          filter: `drop-shadow(0 0 4px ${color})`,
          pointerEvents: 'none',
        }}
      />

      {/* Main edge */}
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={color}
        strokeWidth={isActive ? 2.5 : 2}
        strokeDasharray="6 6"
        opacity={isActive ? 0.9 : 0.65}
        style={{
          transition: 'opacity 0.2s, stroke-width 0.2s',
          cursor: 'pointer',
          filter: isActive ? `drop-shadow(0 0 3px ${color}40)` : undefined,
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />

      {/* Label */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'none',
            fontFamily: 'DM Sans, sans-serif',
            fontSize: '10px',
            fontWeight: 500,
            color: 'var(--text-tertiary)',
            background: 'var(--bg-surface)',
            padding: '2px 6px',
            borderRadius: '4px',
            border: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
            whiteSpace: 'nowrap',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          }}
        >
          <AlertTriangle size={10} strokeWidth={2} style={{ color: 'var(--text-tertiary)' }} />
          {data?.description
            ? data.description.split(' ').slice(0, 5).join(' ') + (data.description.split(' ').length > 5 ? '...' : '')
            : 'Contradiction'}
        </div>
      </EdgeLabelRenderer>

      {/* Hover tooltip */}
      {isActive && data?.factA && data?.factB && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -100%) translate(${labelX}px, ${labelY - 20}px)`,
              pointerEvents: 'none',
              fontFamily: 'DM Sans, sans-serif',
              fontSize: '11px',
              background: 'var(--bg-surface)',
              border: `1px solid ${color}40`,
              borderRadius: '6px',
              padding: '10px 12px',
              boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
              maxWidth: '300px',
              zIndex: 1000,
            }}
          >
            <div style={{ marginBottom: '8px', color, fontWeight: 600, fontSize: '10px', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              {severity.toUpperCase()} Contradiction
            </div>
            <div style={{ marginBottom: '6px' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: 500 }}>A: </span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {data.factA.slice(0, 120)}{data.factA.length > 120 ? '…' : ''}
              </span>
            </div>
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: 500 }}>B: </span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {data.factB.slice(0, 120)}{data.factB.length > 120 ? '…' : ''}
              </span>
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const ContradictionThread = memo(ContradictionThreadComponent);
