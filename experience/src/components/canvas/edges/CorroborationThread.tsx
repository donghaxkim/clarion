'use client';

import React, { memo } from 'react';
import {
  EdgeProps,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Edge,
} from '@xyflow/react';

export interface CorroborationThreadData {
  description: string;
  [key: string]: unknown;
}

export type CorroborationThreadEdge = Edge<CorroborationThreadData, 'corroborationThread'>;

function CorroborationThreadComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<CorroborationThreadEdge>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: 'var(--thread-corroboration, #6B9B7E)',
          strokeWidth: selected ? 1.5 : 1,
          strokeDasharray: '4 4',
          opacity: selected ? 0.6 : 0.3,
          transition: 'opacity 0.2s',
        }}
      />
      {data?.description && selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
              fontFamily: 'DM Sans, sans-serif',
              fontSize: '10px',
              color: '#6B9B7E',
              background: 'var(--bg)',
              padding: '1px 5px',
              borderRadius: '3px',
              border: '1px solid rgba(107,155,126,0.2)',
              whiteSpace: 'nowrap',
            }}
          >
            ✓ {data.description}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const CorroborationThread = memo(CorroborationThreadComponent);
