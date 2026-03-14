'use client';

import { useEffect } from 'react';
import { Edge, useReactFlow, useViewport } from '@xyflow/react';

/** Edge type visibility thresholds */
const ZOOM_THRESHOLDS: Record<string, number> = {
  contradictionThread: 0,      // Always visible
  entityThread: 0.5,           // Show when zoomed in past 0.5x
  corroborationThread: 0.7,    // Show when zoomed in past 0.7x
  timelineThread: 0.7,         // Show when zoomed in past 0.7x
};

export function useZoomVisibility() {
  const { zoom } = useViewport();
  const { setEdges } = useReactFlow();

  useEffect(() => {
    setEdges((edges: Edge[]) =>
      edges.map((edge) => {
        const threshold = ZOOM_THRESHOLDS[edge.type ?? ''] ?? 0;
        const shouldBeVisible = zoom >= threshold;

        // Only update if visibility changes
        const currentlyHidden = edge.hidden === true;
        if (shouldBeVisible && currentlyHidden) {
          return { ...edge, hidden: false };
        } else if (!shouldBeVisible && !currentlyHidden) {
          return { ...edge, hidden: true };
        }
        return edge;
      })
    );
  }, [zoom, setEdges]);
}
