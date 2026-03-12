'use client';

import React, { memo } from 'react';
import {
  EdgeProps,
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  MarkerType,
  Edge,
} from '@xyflow/react';

export interface TimelineThreadData {
  timeGap?: string;
  [key: string]: unknown;
}

export type TimelineThreadEdge = Edge<TimelineThreadData, 'timelineThread'>;

function TimelineThreadComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerEnd,
}: EdgeProps<TimelineThreadEdge>) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
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
        markerEnd={markerEnd ?? `url(#timeline-arrow-${id})`}
        style={{
          stroke: 'var(--thread-timeline, #4A6FA5)',
          strokeWidth: selected ? 1.5 : 1,
          strokeDasharray: '3 3',
          opacity: selected ? 0.5 : 0.3,
          transition: 'opacity 0.2s',
        }}
      />
      {/* Custom arrow marker */}
      <defs>
        <marker
          id={`timeline-arrow-${id}`}
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
        >
          <path d="M 0 0 L 6 3 L 0 6 Z" fill="#4A6FA5" opacity={selected ? 0.5 : 0.3} />
        </marker>
      </defs>
      {data?.timeGap && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
              fontFamily: 'DM Mono, monospace',
              fontSize: '10px',
              color: '#4A6FA5',
              opacity: selected ? 0.8 : 0.5,
              background: 'var(--bg)',
              padding: '1px 4px',
              borderRadius: '3px',
              whiteSpace: 'nowrap',
            }}
          >
            → {data.timeGap}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const TimelineThread = memo(TimelineThreadComponent);
