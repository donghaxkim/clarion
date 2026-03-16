'use client';

import { Edge, Node } from '@xyflow/react';
import { AnalysisResponse } from '@/lib/types';

/** Build React Flow edges from an analysis result */
export function buildEdgesFromAnalysis(
  analysis: AnalysisResponse,
  evidenceNodes: Node[]
): Edge[] {
  const edges: Edge[] = [];
  const nodeIds = new Set(evidenceNodes.map((n) => n.id));
  const evidenceIdToNodeId = new Map<string, string>();

  evidenceNodes.forEach((node) => {
    const nodeData = node.data as { evidenceId?: string };
    const backendEvidenceId = nodeData.evidenceId;
    if (backendEvidenceId) {
      evidenceIdToNodeId.set(backendEvidenceId, node.id);
    }
  });

  // ── Entity threads: connect evidence nodes that share an entity ──────────
  analysis.entities.forEach((entity) => {
    // Collect all evidence IDs that mention this entity
    const mentioningEvidenceIds: string[] = [];

    evidenceNodes.forEach((node) => {
      const nodeData = node.data as { entities?: { name: string }[] };
      const entities = nodeData.entities ?? [];
      if (entities.some((e) => e.name === entity.name)) {
        mentioningEvidenceIds.push(node.id);
      }
    });

    // Create edges between each pair (fully connected sub-graph)
    for (let i = 0; i < mentioningEvidenceIds.length; i++) {
      for (let j = i + 1; j < mentioningEvidenceIds.length; j++) {
        const srcId = mentioningEvidenceIds[i];
        const tgtId = mentioningEvidenceIds[j];
        if (nodeIds.has(srcId) && nodeIds.has(tgtId)) {
          edges.push({
            id: `entity-${entity.id}-${i}-${j}`,
            source: srcId,
            target: tgtId,
            type: 'entityThread',
            data: { entityName: entity.name, entityType: entity.type },
            animated: false,
          });
        }
      }
    }
  });

  // ── Contradiction threads ────────────────────────────────────────────────
  analysis.contradictions.items.forEach((contradiction) => {
    const srcId = evidenceIdToNodeId.get(contradiction.fact_a.evidence_id);
    const tgtId = evidenceIdToNodeId.get(contradiction.fact_b.evidence_id);

    if (
      srcId &&
      tgtId &&
      srcId !== tgtId &&
      nodeIds.has(srcId) &&
      nodeIds.has(tgtId)
    ) {
      edges.push({
        id: `contradiction-${contradiction.id}`,
        source: srcId,
        target: tgtId,
        type: 'contradictionThread',
        data: {
          severity: contradiction.severity,
          description: contradiction.description,
          factA: contradiction.fact_a.text,
          factB: contradiction.fact_b.text,
        },
        animated: true,
      });
    }
  });

  return edges;
}

/** Stagger edge reveal — returns a function that reveals edges one by one */
export function staggerEdgeReveal(
  edges: Edge[],
  setEdges: (updater: (edges: Edge[]) => Edge[]) => void,
  options: {
    delayPerEdge?: number;
    contradictionDelay?: number;
    entityFirst?: boolean;
  } = {}
): Promise<void> {
  const {
    delayPerEdge = 200,
    contradictionDelay = 300,
  } = options;

  const entityEdges = edges.filter((e) => e.type === 'entityThread');
  const contradictionEdges = edges.filter((e) => e.type === 'contradictionThread');
  const otherEdges = edges.filter(
    (e) => e.type !== 'entityThread' && e.type !== 'contradictionThread'
  );

  return new Promise<void>((resolve) => {
    let totalDelay = 0;

    // First, add other edges
    otherEdges.forEach((edge, i) => {
      setTimeout(() => {
        setEdges((prev) => [
          ...prev,
          { ...edge, className: 'edge-draw-in', style: { opacity: 1 } },
        ]);
      }, totalDelay + i * delayPerEdge);
    });
    totalDelay += otherEdges.length * delayPerEdge;

    // Then entity edges
    entityEdges.forEach((edge, i) => {
      setTimeout(() => {
        setEdges((prev) => [
          ...prev,
          { ...edge, className: 'edge-draw-in', style: { opacity: 0.4 } },
        ]);
      }, totalDelay + i * delayPerEdge);
    });
    totalDelay += entityEdges.length * delayPerEdge + contradictionDelay;

    // Finally contradiction edges (with drama)
    contradictionEdges.forEach((edge, i) => {
      setTimeout(() => {
        setEdges((prev) => [
          ...prev,
          {
            ...edge,
            className: 'edge-draw-in edge-contradiction-animated',
            style: { opacity: 0.7 },
          },
        ]);
        if (i === contradictionEdges.length - 1) {
          setTimeout(resolve, delayPerEdge);
        }
      }, totalDelay + i * (delayPerEdge + 100));
    });

    if (contradictionEdges.length === 0) {
      setTimeout(resolve, totalDelay);
    }
  });
}
