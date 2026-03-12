'use client';

import { useCallback, useRef } from 'react';
import { Node, useReactFlow } from '@xyflow/react';
import { computeClusterLayout } from '../utils/layout';
import type { EvidenceNodeData } from '../nodes/EvidenceNode';

type EvidenceNode = Node<EvidenceNodeData, 'evidenceNode'>;

interface UseAutoClusterOptions {
  onClusterStart?: () => void;
  onClusterEnd?: () => void;
}

/** Find the cluster label node that owns a given evidence node */
export function getClusterForNode(nodeId: string, allNodes: Node[]): Node | undefined {
  return allNodes.find(
    (n) =>
      n.type === 'clusterLabel' &&
      Array.isArray((n.data as Record<string, unknown>).childIds) &&
      ((n.data as Record<string, unknown>).childIds as string[]).includes(nodeId)
  );
}

export function useAutoCluster(options: UseAutoClusterOptions = {}) {
  const { setNodes, getNodes } = useReactFlow();
  const isClusteringRef = useRef(false);

  const cluster = useCallback(
    (targetNodes?: EvidenceNode[]) => {
      if (isClusteringRef.current) return;

      const allNodes = getNodes() as Node[];
      const evidenceNodes = (targetNodes ?? allNodes.filter((n) => n.type === 'evidenceNode')) as EvidenceNode[];

      if (evidenceNodes.length === 0) return;

      isClusteringRef.current = true;
      options.onClusterStart?.();

      const positions = computeClusterLayout(evidenceNodes);

      setNodes((prev) => {
        const posMap = new Map(positions.map((p) => [p.id, p]));

        // Remove old cluster labels
        const filtered = prev.filter((n) => n.type !== 'clusterLabel');

        // Update evidence node positions
        const updated = filtered.map((node) => {
          const pos = posMap.get(node.id);
          if (pos && node.type === 'evidenceNode') {
            return { ...node, position: { x: pos.x, y: pos.y } };
          }
          return node;
        });

        // Add new cluster labels
        const labelPositions = positions.filter((p) => p.type === 'clusterLabel');
        const labelNodes: Node[] = labelPositions.map((lp) => ({
          id: lp.id,
          type: 'clusterLabel',
          position: { x: lp.x, y: lp.y },
          data: lp.data ?? {},
          selectable: false,
        }));

        return [...updated, ...labelNodes];
      });

      // End cluster animation flag after transition completes
      setTimeout(() => {
        isClusteringRef.current = false;
        options.onClusterEnd?.();
      }, 900);
    },
    [getNodes, setNodes, options]
  );

  return { cluster };
}
