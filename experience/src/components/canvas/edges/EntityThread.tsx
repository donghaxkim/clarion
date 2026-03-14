'use client';

import React, { memo } from 'react';
import {
  EdgeProps,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Edge,
} from '@xyflow/react';
import { getEntityTypeColor } from '../utils/thumbnail';

export interface EntityThreadData {
  entityName: string;
  entityType: string;
  [key: string]: unknown;
}

export type EntityThreadEdge = Edge<EntityThreadData, 'entityThread'>;

function EntityThreadComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<EntityThreadEdge>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const entityColor = getEntityTypeColor(data?.entityType ?? 'other');

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: 'var(--thread-entity, #C0BDB4)',
          strokeWidth: selected ? 2 : 1,
          opacity: selected ? 0.8 : 0.4,
          transition: 'opacity 0.2s, stroke-width 0.2s',
          strokeDasharray: undefined,
        }}
      />
      {data?.entityName && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
              fontFamily: 'DM Sans, sans-serif',
              fontSize: '10px',
              color: 'var(--text-tertiary)',
              background: 'var(--bg)',
              padding: '1px 5px',
              borderRadius: '3px',
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
              opacity: selected ? 1 : 0,
              transition: 'opacity 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            <span
              style={{
                width: '5px',
                height: '5px',
                borderRadius: '50%',
                background: entityColor,
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            {data.entityName}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const EntityThread = memo(EntityThreadComponent);
