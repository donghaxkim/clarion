'use client';

import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
  createContext,
  useContext,
} from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  NodeTypes,
  EdgeTypes,
  Node,
  Edge,
  NodeChange,
  EdgeChange,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { EvidenceNode, EvidenceNodeData } from './nodes/EvidenceNode';
import { ClusterLabel } from './nodes/ClusterLabel';
import { InsightBadge } from './nodes/InsightBadge';
import { EntityThread } from './edges/EntityThread';
import { ContradictionThread } from './edges/ContradictionThread';
import { CorroborationThread } from './edges/CorroborationThread';
import { TimelineThread } from './edges/TimelineThread';
import { CanvasToolbar } from './controls/CanvasToolbar';
import { ZoomControls } from './controls/ZoomControls';
import { useAutoCluster, getClusterForNode } from './hooks/useAutoCluster';
import { useFileDrop } from './hooks/useFileDrop';
import { useZoomVisibility } from './hooks/useZoomVisibility';
import { buildEdgesFromAnalysis, staggerEdgeReveal } from './hooks/useEdgeBuilder';
import { computeClusterLayout } from './utils/layout';

import { ParsedEvidence, AnalysisResponse } from '@/lib/types';
import { createCase, uploadFiles, analyzeCase, generateReport, streamReport } from '@/lib/api';
import { ReportProgressSidebar, SectionState } from '@/components/report/ReportProgressSidebar';
import { AgentOrb } from '@/components/agent/AgentOrb';
import {
  MOCK_CASE_ID,
  MOCK_EVIDENCE,
  MOCK_ANALYSIS,
} from '@/lib/mock-data';

// ─── Context ───────────────────────────────────────────────────────────────────

interface CanvasCtx {
  connectedNodeIds: Set<string>;
}

const CanvasContext = createContext<CanvasCtx>({ connectedNodeIds: new Set() });

// ─── Node / Edge Types ─────────────────────────────────────────────────────────

const nodeTypes: NodeTypes = {
  evidenceNode: EvidenceNode,
  clusterLabel: ClusterLabel,
  insightBadge: InsightBadge,
};

const edgeTypes: EdgeTypes = {
  entityThread: EntityThread,
  contradictionThread: ContradictionThread,
  corroborationThread: CorroborationThread,
  timelineThread: TimelineThread,
};

// ─── Helpers ───────────────────────────────────────────────────────────────────

function evidenceToNode(ev: ParsedEvidence, position: { x: number; y: number }): Node<EvidenceNodeData> {
  return {
    id: ev.evidence_id,
    type: 'evidenceNode',
    position,
    data: {
      evidenceId: ev.evidence_id,
      filename: ev.filename,
      evidenceType: ev.evidence_type,
      summary: ev.summary,
      entities: ev.entities,
      entityCount: ev.entity_count,
      factCount: 0,
      labels: ev.labels,
      nodeStatus: ev.status === 'parsed' ? 'complete' : 'parsing',
      hasConnections: false,
    },
  };
}

function buildInitialMockNodes(): Node[] {
  const evidenceNodes = MOCK_EVIDENCE.map((ev, i) => ({
    id: ev.evidence_id,
    type: 'evidenceNode' as const,
    position: { x: (i % 3) * 300, y: Math.floor(i / 3) * 400 },
    data: {
      evidenceId: ev.evidence_id,
      filename: ev.filename,
      evidenceType: ev.evidence_type,
      summary: ev.summary,
      entities: ev.entities,
      entityCount: ev.entity_count,
      factCount: 6 + i * 2,
      labels: ev.labels,
      nodeStatus: 'complete' as const,
      hasConnections: false,
    } satisfies EvidenceNodeData,
  }));

  // Compute clustered positions
  const positions = computeClusterLayout(evidenceNodes);
  const posMap = new Map(positions.map((p) => [p.id, p]));

  const positionedNodes: Node[] = evidenceNodes.map((n) => {
    const pos = posMap.get(n.id);
    return pos ? { ...n, position: { x: pos.x, y: pos.y } } : n;
  });

  // Add cluster labels
  const labelNodes: Node[] = positions
    .filter((p) => p.type === 'clusterLabel')
    .map((lp) => ({
      id: lp.id,
      type: 'clusterLabel',
      position: { x: lp.x, y: lp.y },
      data: lp.data ?? {},
      selectable: false,
    }));

  return [...positionedNodes, ...labelNodes];
}

function buildInitialMockEdges(nodes: Node[]): Edge[] {
  const evidenceNodes = nodes.filter((n) => n.type === 'evidenceNode');
  const edges = buildEdgesFromAnalysis(MOCK_ANALYSIS, evidenceNodes);
  return edges.map((e) => ({
    ...e,
    style: {
      opacity: e.type === 'contradictionThread' ? 0.65 : 0.4,
    },
    className: e.type === 'contradictionThread' ? 'edge-contradiction-animated' : undefined,
  }));
}

// ─── Inner Canvas (uses useReactFlow) ─────────────────────────────────────────

function EvidenceCanvasInner() {
  const { fitView } = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);

  const initialNodes = useMemo(() => buildInitialMockNodes(), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);

  // Keep a ref to nodes so handleNodesChange can read pre-change positions
  // without being recreated on every node update
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;

  const initialEdges = useMemo(() => buildInitialMockEdges(initialNodes), [initialNodes]);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const [caseId, setCaseId] = useState<string | null>(MOCK_CASE_ID);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(MOCK_ANALYSIS);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisDone, setAnalysisDone] = useState(true); // true because mock data shows analysis done
  const [isReclustering, setIsReclustering] = useState(false);
  const [showAnalyzeWave, setShowAnalyzeWave] = useState(false);

  // Report sidebar state
  const [reportSidebarOpen, setReportSidebarOpen] = useState(false);
  const [reportSections, setReportSections] = useState<SectionState[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [reportDone, setReportDone] = useState(false);

  // Fit view after mount
  useEffect(() => {
    const timer = setTimeout(() => fitView({ duration: 600, padding: 0.12 }), 200);
    return () => clearTimeout(timer);
  }, [fitView]);

  // Zoom-based edge visibility
  useZoomVisibility();

  // Auto-cluster hook
  const { cluster } = useAutoCluster({
    onClusterStart: () => setIsReclustering(true),
    onClusterEnd: () => setIsReclustering(false),
  });

  // Track which nodes have connections
  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    edges.forEach((e) => {
      ids.add(e.source);
      ids.add(e.target);
    });
    return ids;
  }, [edges]);

  // Update node data when connections change
  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => {
        if (node.type !== 'evidenceNode') return node;
        const hasConnections = connectedNodeIds.has(node.id);
        if ((node.data as EvidenceNodeData).hasConnections !== hasConnections) {
          return { ...node, data: { ...node.data, hasConnections } };
        }
        return node;
      })
    );
  }, [connectedNodeIds, setNodes]);

  // ── Snap-back animation state ───────────────────────────────────────────
  const [isSnappingBack, setIsSnappingBack] = useState(false);

  // ── Handle node drag: group-drag for clusters + snap-back for cards ────
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Read pre-change positions from ref (before onNodesChange mutates state)
      const preNodes = nodesRef.current;
      const extraChanges: NodeChange[] = [];

      for (const change of changes) {
        if (change.type !== 'position' || !change.dragging || !change.position) continue;

        const node = preNodes.find((n) => n.id === change.id);
        if (!node || node.type !== 'clusterLabel') continue;

        const childIds = (node.data as Record<string, unknown>).childIds as string[] | undefined;
        if (!childIds?.length) continue;

        const dx = change.position.x - node.position.x;
        const dy = change.position.y - node.position.y;
        if (dx === 0 && dy === 0) continue;

        // Inject position changes for every child so they move with the header
        for (const childId of childIds) {
          const child = preNodes.find((n) => n.id === childId);
          if (child) {
            extraChanges.push({
              type: 'position',
              id: childId,
              position: { x: child.position.x + dx, y: child.position.y + dy },
            } as NodeChange);
          }
        }
      }

      // Apply original + child-movement changes together
      onNodesChange([...changes, ...extraChanges]);

      // Post-change bookkeeping
      const pinIds: string[] = [];
      const snapBacks: { id: string; pos: { x: number; y: number } }[] = [];
      const validUpdates: { id: string; pos: { x: number; y: number } }[] = [];

      for (const change of changes) {
        if (change.type !== 'position') continue;

        const preNode = preNodes.find((n) => n.id === change.id);
        if (!preNode) continue;

        // Pin evidence nodes when dragged
        if (change.dragging && preNode.type === 'evidenceNode') {
          pinIds.push(change.id);
        }

        // On drag end: snap-back check
        if (!change.dragging && change.position && preNode.type === 'evidenceNode') {
          const cluster = getClusterForNode(change.id, preNodes);
          if (!cluster) continue;

          const childIds = (cluster.data as Record<string, unknown>).childIds as string[];
          const siblings = preNodes.filter(
            (n) => childIds.includes(n.id) && n.id !== change.id
          );
          if (siblings.length === 0) continue;

          let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
          for (const s of siblings) {
            minX = Math.min(minX, s.position.x);
            minY = Math.min(minY, s.position.y);
            maxX = Math.max(maxX, s.position.x);
            maxY = Math.max(maxY, s.position.y);
          }

          const margin = 150;
          const { x, y } = change.position;

          if (x < minX - margin || x > maxX + margin || y < minY - margin || y > maxY + margin) {
            // Snap back — use lastValidPosition, or the position it had before this drag
            const lastValid = (preNode.data as Record<string, unknown>).lastValidPosition as
              | { x: number; y: number }
              | undefined;
            snapBacks.push({ id: change.id, pos: lastValid ?? preNode.position });
          } else {
            validUpdates.push({ id: change.id, pos: change.position });
          }
        }
      }

      // Apply pins, snap-backs, and valid-position updates in one batch
      if (pinIds.length > 0 || snapBacks.length > 0 || validUpdates.length > 0) {
        if (snapBacks.length > 0) {
          setIsSnappingBack(true);
          setTimeout(() => setIsSnappingBack(false), 400);
        }

        const snapMap = new Map(snapBacks.map((s) => [s.id, s.pos]));
        const validMap = new Map(validUpdates.map((v) => [v.id, v.pos]));
        const pinSet = new Set(pinIds);

        setNodes((prev) =>
          prev.map((n) => {
            const snap = snapMap.get(n.id);
            if (snap) return { ...n, position: snap };

            let updated = n;
            if (pinSet.has(n.id) && !(n.data as Record<string, unknown>).pinned) {
              updated = { ...updated, data: { ...updated.data, pinned: true } };
            }
            const vPos = validMap.get(n.id);
            if (vPos) {
              updated = { ...updated, data: { ...updated.data, lastValidPosition: vPos } };
            }
            return updated;
          })
        );
      }
    },
    [onNodesChange, setNodes]
  );

  // ── File handling ────────────────────────────────────────────────────────

  const handleFiles = useCallback(
    async (files: File[], position: { x: number; y: number }) => {
      let id = caseId;
      if (!id) {
        try {
          const res = await createCase({});
          id = res.case_id;
        } catch {
          id = MOCK_CASE_ID;
        }
        setCaseId(id);
      }

      // Spread multiple files slightly from the drop point
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const nodeId = `upload-${Date.now()}-${i}`;
        const filePos = {
          x: position.x + i * 20 - (files.length * 10),
          y: position.y + i * 20,
        };

        // Add uploading node
        const uploadingNode: Node<EvidenceNodeData> = {
          id: nodeId,
          type: 'evidenceNode',
          position: filePos,
          data: {
            evidenceId: nodeId,
            filename: file.name,
            evidenceType: 'other',
            summary: '',
            entities: [],
            entityCount: 0,
            factCount: 0,
            labels: [],
            nodeStatus: 'uploading',
            uploadProgress: 0,
            hasConnections: false,
          },
        };

        setNodes((prev) => [...prev, uploadingNode]);

        // Upload
        try {
          await uploadFiles(id!, [file], (ev: ParsedEvidence) => {
            setNodes((prev) =>
              prev.map((n) => {
                if (n.id !== nodeId) return n;
                return {
                  ...n,
                  id: ev.evidence_id,
                  data: {
                    ...(n.data as EvidenceNodeData),
                    evidenceId: ev.evidence_id,
                    filename: ev.filename,
                    evidenceType: ev.evidence_type,
                    summary: ev.summary,
                    entities: ev.entities,
                    entityCount: ev.entity_count,
                    labels: ev.labels,
                    nodeStatus: 'complete' as const,
                    uploadProgress: 100,
                  },
                };
              })
            );

            // Trigger recluster
            setTimeout(() => {
              setNodes((prev) => {
                const evidenceNodes = prev.filter((n) => n.type === 'evidenceNode');
                cluster(evidenceNodes as any);
                return prev;
              });
            }, 100);
          });
        } catch {
          // On error, show as complete with mock data
          setNodes((prev) =>
            prev.map((n) =>
              n.id === nodeId
                ? {
                    ...n,
                    data: {
                      ...(n.data as EvidenceNodeData),
                      nodeStatus: 'complete' as const,
                      uploadProgress: 100,
                    },
                  }
                : n
            )
          );
        }
      }
    },
    [caseId, setNodes, cluster]
  );

  const handleAddFilesFromButton = useCallback(
    (files: File[]) => {
      const viewport = { x: 0, y: 0 };
      handleFiles(files, viewport);
    },
    [handleFiles]
  );

  // ── Drop zone ────────────────────────────────────────────────────────────
  const { isDragOver, dropLabelPos, handlers: dropHandlers } = useFileDrop({
    onFiles: handleFiles,
  });

  // ── Analyze ──────────────────────────────────────────────────────────────
  const handleAnalyze = useCallback(async () => {
    const evidenceNodes = nodes.filter((n) => n.type === 'evidenceNode');
    if (evidenceNodes.length === 0 || isAnalyzing) return;

    setIsAnalyzing(true);

    // Step 1: Pulse all nodes amber
    setNodes((prev) =>
      prev.map((n) =>
        n.type === 'evidenceNode'
          ? { ...n, data: { ...n.data, analyzing: true } }
          : n
      )
    );

    // Step 2: Radial wave
    setShowAnalyzeWave(true);
    setTimeout(() => setShowAnalyzeWave(false), 1600);

    // Step 3: Call API
    let result: AnalysisResponse | null = null;
    try {
      result = await analyzeCase(caseId!);
    } catch {
      result = MOCK_ANALYSIS;
    }
    setAnalysisResult(result);

    // Step 4: Recluster nodes (animated)
    await new Promise<void>((resolve) => {
      setNodes((prev) => {
        const ev = prev.filter((n) => n.type === 'evidenceNode');
        cluster(ev as any);
        return prev.map((n) =>
          n.type === 'evidenceNode'
            ? { ...n, data: { ...n.data, analyzing: false } }
            : n
        );
      });
      setTimeout(resolve, 900);
    });

    // Step 5: Clear existing edges, build new ones
    setEdges([]);
    const currentEvidenceNodes = nodes.filter((n) => n.type === 'evidenceNode');
    const newEdges = buildEdgesFromAnalysis(result, currentEvidenceNodes);

    // Step 6: Stagger edge reveal
    await staggerEdgeReveal(newEdges, setEdges);

    // Step 7: Add insight badges
    if (result.contradictions.items.length > 0) {
      const badgeId = 'insight-contradiction-count';
      const midNode = nodes[Math.floor(nodes.length / 2)];
      const badgePos = midNode?.position ?? { x: 200, y: 200 };

      setNodes((prev) => [
        ...prev,
        {
          id: badgeId,
          type: 'insightBadge',
          position: { x: badgePos.x + 80, y: badgePos.y - 80 },
          data: {
            insightType: 'contradiction',
            text: `${result!.contradictions.summary.total} contradiction${result!.contradictions.summary.total > 1 ? 's' : ''} found`,
          },
          draggable: false,
          selectable: false,
        },
      ]);
    }

    setAnalysisDone(true);
    setIsAnalyzing(false);
  }, [nodes, isAnalyzing, caseId, setNodes, setEdges, cluster]);

  // ── Generate Report (inline sidebar) ────────────────────────────────────
  const handleGenerateReport = useCallback(() => {
    if (isGenerating || reportSidebarOpen || !caseId) return;
    setReportSidebarOpen(true);
    setIsGenerating(true);
    setReportDone(false);
    setReportSections([]);

    generateReport(caseId).catch(() => {/* non-fatal */});

    streamReport(
      caseId,
      (event) => {
        if (event.event === 'section_start') {
          setReportSections((prev) => [
            ...prev,
            { section: event.section, text: '', streaming: true, complete: false },
          ]);
        } else if (event.event === 'section_delta') {
          setReportSections((prev) =>
            prev.map((s) =>
              s.section.id === event.section_id
                ? { ...s, text: s.text + event.delta_text }
                : s
            )
          );
        } else if (event.event === 'section_complete') {
          setReportSections((prev) =>
            prev.map((s) =>
              s.section.id === event.section_id
                ? { ...s, streaming: false, complete: true }
                : s
            )
          );
        } else if (event.event === 'done') {
          setIsGenerating(false);
          setReportDone(true);
        }
      },
      () => {
        setIsGenerating(false);
        setReportDone(true);
      }
    );
  }, [isGenerating, reportSidebarOpen, caseId]);

  const handleAnalyzeAndGenerate = useCallback(async () => {
    await handleAnalyze();
    handleGenerateReport();
  }, [handleAnalyze, handleGenerateReport]);

  // ── Reset layout ─────────────────────────────────────────────────────
  const handleResetLayout = useCallback(() => {
    const resetNodes = buildInitialMockNodes();
    setNodes(resetNodes);
    const resetEdges = buildInitialMockEdges(resetNodes);
    setEdges(resetEdges);
    setTimeout(() => fitView({ duration: 600, padding: 0.12 }), 50);
  }, [setNodes, setEdges, fitView]);

  const evidenceCount = nodes.filter((n) => n.type === 'evidenceNode').length;

  return (
    <CanvasContext.Provider value={{ connectedNodeIds }}>
      <div
        ref={wrapperRef}
        style={{ width: '100%', height: '100%', display: 'flex' }}
        {...dropHandlers}
      >
        {/* Canvas area */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {/* Canvas recluster class */}
          <div
            className={[
              isReclustering ? 'is-reclustering' : '',
              isSnappingBack ? 'is-snapping-back' : '',
            ].filter(Boolean).join(' ') || undefined}
            style={{ width: '100%', height: '100%' }}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={handleNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              fitViewOptions={{ padding: 0.12 }}
              panOnDrag
              zoomOnScroll
              selectionOnDrag={false}
              minZoom={0.15}
              maxZoom={2}
              style={{ background: 'var(--bg)' }}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={20}
                size={1.5}
                color="#E8E6E0"
              />

              {/* Toolbar */}
              <CanvasToolbar
                evidenceCount={evidenceCount}
                isAnalyzing={isAnalyzing}
                isGenerating={isGenerating}
                caseId={caseId}
                onAddFiles={handleAddFilesFromButton}
                onGenerateReport={handleAnalyzeAndGenerate}
              />

              {/* Zoom Controls */}
              <ZoomControls onReset={handleResetLayout} />
            </ReactFlow>
          </div>

          {/* Drag-over overlay */}
          {isDragOver && (
            <div className="canvas-dragover-overlay">
              <div
                style={{
                  position: 'absolute',
                  left: dropLabelPos.x - 80,
                  top: dropLabelPos.y - 20,
                  fontFamily: 'DM Sans, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: 'var(--accent)',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  pointerEvents: 'none',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>📎</span>
                Drop to add evidence
              </div>
            </div>
          )}

          {/* Analyze wave */}
          {showAnalyzeWave && <div className="canvas-analyze-wave" />}

          {/* Agent Orb — positioned within canvas area so it shifts with sidebar */}
          <div style={{ position: 'absolute', bottom: '24px', right: '24px', zIndex: 50, width: '80px' }}>
            <AgentOrb />
          </div>
        </div>

        {/* Report progress sidebar */}
        {reportSidebarOpen && (
          <ReportProgressSidebar
            sections={reportSections}
            isGenerating={isGenerating}
            done={reportDone}
            caseId={caseId}
          />
        )}
      </div>
    </CanvasContext.Provider>
  );
}

// ─── Public Export (wrapped in ReactFlowProvider) ─────────────────────────────

interface EvidenceCanvasProps {
  caseId?: string;
}

export function EvidenceCanvas({ caseId: _caseId }: EvidenceCanvasProps = {}) {
  return (
    <ReactFlowProvider>
      <EvidenceCanvasInner />
    </ReactFlowProvider>
  );
}
