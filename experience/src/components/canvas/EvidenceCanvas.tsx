'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Edge,
  EdgeChange,
  EdgeTypes,
  Node,
  NodeChange,
  NodeTypes,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { AgentOrb } from '@/components/agent/AgentOrb';
import { ReportProgressSidebar, SectionState } from '@/components/report/ReportProgressSidebar';
import {
  analyzeCase,
  createCase,
  generateReport,
  getReportJob,
  streamReport,
  uploadFiles,
} from '@/lib/api';
import { MOCK_ANALYSIS, MOCK_CASE_ID, MOCK_CASE_TITLE, MOCK_EVIDENCE } from '@/lib/mock-data';
import { AnalysisResponse, ParsedEvidence, ReportSection } from '@/lib/types';

import { CanvasToolbar } from './controls/CanvasToolbar';
import { ZoomControls } from './controls/ZoomControls';
import { ContradictionThread } from './edges/ContradictionThread';
import { CorroborationThread } from './edges/CorroborationThread';
import { EntityThread } from './edges/EntityThread';
import { TimelineThread } from './edges/TimelineThread';
import { useAutoCluster, getClusterForNode } from './hooks/useAutoCluster';
import { buildEdgesFromAnalysis, staggerEdgeReveal } from './hooks/useEdgeBuilder';
import { useFileDrop } from './hooks/useFileDrop';
import { useZoomVisibility } from './hooks/useZoomVisibility';
import { ClusterLabel } from './nodes/ClusterLabel';
import { EvidenceNode, EvidenceNodeData } from './nodes/EvidenceNode';
import { InsightBadge } from './nodes/InsightBadge';
import { computeClusterLayout } from './utils/layout';

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const DEFAULT_CASE_TITLE = 'Untitled Matter';

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

export interface WorkspaceSummary {
  caseId: string | null;
  title: string;
  statusText: string;
  evidenceCount: number;
}

type EvidenceCanvasNode = Node<EvidenceNodeData, 'evidenceNode'>;

function buildInitialMockNodes(): Node[] {
  const evidenceNodes = MOCK_EVIDENCE.map((ev, index) => ({
    id: ev.evidence_id,
    type: 'evidenceNode' as const,
    position: { x: (index % 3) * 300, y: Math.floor(index / 3) * 400 },
    data: {
      evidenceId: ev.evidence_id,
      filename: ev.filename,
      evidenceType: ev.evidence_type,
      summary: ev.summary,
      entities: ev.entities,
      entityCount: ev.entity_count,
      factCount: 6 + index * 2,
      labels: ev.labels,
      nodeStatus: 'complete' as const,
      isIndexed: true,
      hasConnections: false,
    } satisfies EvidenceNodeData,
  }));

  const positions = computeClusterLayout(evidenceNodes);
  const positionMap = new Map(positions.map((item) => [item.id, item]));

  const positionedEvidenceNodes: Node[] = evidenceNodes.map((node) => {
    const position = positionMap.get(node.id);
    return position ? { ...node, position: { x: position.x, y: position.y } } : node;
  });

  const clusterLabelNodes: Node[] = positions
    .filter((item) => item.type === 'clusterLabel')
    .map((item) => ({
      id: item.id,
      type: 'clusterLabel',
      position: { x: item.x, y: item.y },
      data: item.data ?? {},
      selectable: false,
    }));

  return [...positionedEvidenceNodes, ...clusterLabelNodes];
}

function updateEvidenceNodeByFlowId(
  flowNodeId: string,
  updater: (node: EvidenceCanvasNode) => EvidenceCanvasNode,
) {
  return (prev: Node[]) =>
    prev.map((node) =>
      isEvidenceCanvasNode(node) && node.id === flowNodeId ? updater(node) : node,
    );
}

function buildInitialMockEdges(nodes: Node[]): Edge[] {
  const evidenceNodes = nodes.filter((node) => node.type === 'evidenceNode');
  return buildEdgesFromAnalysis(MOCK_ANALYSIS, evidenceNodes).map((edge) => ({
    ...edge,
    style: {
      opacity: edge.type === 'contradictionThread' ? 0.65 : 0.4,
    },
    className: edge.type === 'contradictionThread' ? 'edge-contradiction-animated' : undefined,
  }));
}

function isEvidenceCanvasNode(node: Node): node is EvidenceCanvasNode {
  return node.type === 'evidenceNode';
}

function buildWorkspaceStatusText({
  evidenceCount,
  isAnalyzing,
  isGenerating,
  analysisDone,
}: {
  evidenceCount: number;
  isAnalyzing: boolean;
  isGenerating: boolean;
  analysisDone: boolean;
}): string {
  const fileLabel =
    evidenceCount === 0
      ? 'No files indexed'
      : `${evidenceCount} file${evidenceCount === 1 ? '' : 's'} indexed`;

  if (isGenerating) {
    return `${fileLabel} · generating report`;
  }
  if (isAnalyzing) {
    return `${fileLabel} · analyzing`;
  }
  if (analysisDone && evidenceCount > 0) {
    return `${fileLabel} · analyzed`;
  }
  return fileLabel;
}

function buildSectionStates(sections: ReportSection[], status: string): SectionState[] {
  const terminal = status === 'completed' || status === 'failed';
  return sections.map((section, index) => ({
    section,
    text: section.text ?? '',
    streaming: !terminal && index === sections.length - 1,
    complete: terminal || index < sections.length - 1,
  }));
}

function buildInitialNodes() {
  return USE_MOCK ? buildInitialMockNodes() : [];
}

function buildInitialEdges(nodes: Node[]) {
  return USE_MOCK ? buildInitialMockEdges(nodes) : [];
}

function EvidenceCanvasInner({
  onWorkspaceChange,
}: {
  onWorkspaceChange?: (summary: WorkspaceSummary) => void;
}) {
  const { fitView } = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const streamCleanupRef = useRef<(() => void) | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const initialNodes = useMemo(() => buildInitialNodes(), []);
  const initialEdges = useMemo(() => buildInitialEdges(initialNodes), [initialNodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [caseId, setCaseId] = useState<string | null>(USE_MOCK ? MOCK_CASE_ID : null);
  const [caseTitle, setCaseTitle] = useState(USE_MOCK ? MOCK_CASE_TITLE : DEFAULT_CASE_TITLE);
  const [analysisDone, setAnalysisDone] = useState(USE_MOCK);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isReclustering, setIsReclustering] = useState(false);
  const [isSnappingBack, setIsSnappingBack] = useState(false);
  const [showAnalyzeWave, setShowAnalyzeWave] = useState(false);
  const [reportSidebarOpen, setReportSidebarOpen] = useState(false);
  const [reportSections, setReportSections] = useState<SectionState[]>([]);
  const [reportJobId, setReportJobId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [reportDone, setReportDone] = useState(false);

  nodesRef.current = nodes;

  useEffect(() => {
    const timer = window.setTimeout(() => fitView({ duration: 600, padding: 0.12 }), 200);
    return () => window.clearTimeout(timer);
  }, [fitView]);

  useEffect(
    () => () => {
      streamCleanupRef.current?.();
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
    },
    [],
  );

  useZoomVisibility();

  const { cluster } = useAutoCluster({
    onClusterStart: () => setIsReclustering(true),
    onClusterEnd: () => setIsReclustering(false),
  });

  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const edge of edges) {
      ids.add(edge.source);
      ids.add(edge.target);
    }
    return ids;
  }, [edges]);

  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => {
        if (node.type !== 'evidenceNode') {
          return node;
        }
        const hasConnections = connectedNodeIds.has(node.id);
        if ((node.data as EvidenceNodeData).hasConnections === hasConnections) {
          return node;
        }
        return { ...node, data: { ...node.data, hasConnections } };
      }),
    );
  }, [connectedNodeIds, setNodes]);

  const evidenceCount = nodes.filter((node) => node.type === 'evidenceNode').length;
  const indexedEvidenceCount = nodes.filter(
    (node) => node.type === 'evidenceNode' && Boolean((node.data as EvidenceNodeData).isIndexed),
  ).length;

  useEffect(() => {
    onWorkspaceChange?.({
      caseId,
      title: caseTitle,
      statusText: buildWorkspaceStatusText({
        evidenceCount: indexedEvidenceCount,
        isAnalyzing,
        isGenerating,
        analysisDone,
      }),
      evidenceCount: indexedEvidenceCount,
    });
  }, [
    analysisDone,
    caseId,
    caseTitle,
    indexedEvidenceCount,
    isAnalyzing,
    isGenerating,
    onWorkspaceChange,
  ]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const preNodes = nodesRef.current;
      const extraChanges: NodeChange[] = [];

      for (const change of changes) {
        if (change.type !== 'position' || !change.dragging || !change.position) {
          continue;
        }

        const node = preNodes.find((candidate) => candidate.id === change.id);
        if (!node || node.type !== 'clusterLabel') {
          continue;
        }

        const childIds = (node.data as Record<string, unknown>).childIds as string[] | undefined;
        if (!childIds?.length) {
          continue;
        }

        const dx = change.position.x - node.position.x;
        const dy = change.position.y - node.position.y;
        if (dx === 0 && dy === 0) {
          continue;
        }

        for (const childId of childIds) {
          const child = preNodes.find((candidate) => candidate.id === childId);
          if (!child) {
            continue;
          }
          extraChanges.push({
            type: 'position',
            id: childId,
            position: { x: child.position.x + dx, y: child.position.y + dy },
          } as NodeChange);
        }
      }

      onNodesChange([...changes, ...extraChanges]);

      const pinIds: string[] = [];
      const snapBacks: { id: string; pos: { x: number; y: number } }[] = [];
      const validUpdates: { id: string; pos: { x: number; y: number } }[] = [];

      for (const change of changes) {
        if (change.type !== 'position') {
          continue;
        }

        const preNode = preNodes.find((node) => node.id === change.id);
        if (!preNode) {
          continue;
        }

        if (change.dragging && preNode.type === 'evidenceNode') {
          pinIds.push(change.id);
        }

        if (!change.dragging && change.position && preNode.type === 'evidenceNode') {
          const clusterNode = getClusterForNode(change.id, preNodes);
          if (!clusterNode) {
            continue;
          }

          const childIds = (clusterNode.data as Record<string, unknown>).childIds as string[];
          const siblings = preNodes.filter(
            (node) => childIds.includes(node.id) && node.id !== change.id,
          );
          if (siblings.length === 0) {
            continue;
          }

          let minX = Infinity;
          let minY = Infinity;
          let maxX = -Infinity;
          let maxY = -Infinity;

          for (const sibling of siblings) {
            minX = Math.min(minX, sibling.position.x);
            minY = Math.min(minY, sibling.position.y);
            maxX = Math.max(maxX, sibling.position.x);
            maxY = Math.max(maxY, sibling.position.y);
          }

          const margin = 150;
          const { x, y } = change.position;

          if (
            x < minX - margin ||
            x > maxX + margin ||
            y < minY - margin ||
            y > maxY + margin
          ) {
            const lastValid = (preNode.data as Record<string, unknown>).lastValidPosition as
              | { x: number; y: number }
              | undefined;
            snapBacks.push({ id: change.id, pos: lastValid ?? preNode.position });
          } else {
            validUpdates.push({ id: change.id, pos: change.position });
          }
        }
      }

      if (pinIds.length === 0 && snapBacks.length === 0 && validUpdates.length === 0) {
        return;
      }

      if (snapBacks.length > 0) {
        setIsSnappingBack(true);
        window.setTimeout(() => setIsSnappingBack(false), 400);
      }

      const snapMap = new Map(snapBacks.map((item) => [item.id, item.pos]));
      const validMap = new Map(validUpdates.map((item) => [item.id, item.pos]));
      const pinSet = new Set(pinIds);

      setNodes((prev) =>
        prev.map((node) => {
          const snap = snapMap.get(node.id);
          if (snap) {
            return { ...node, position: snap };
          }

          let nextNode = node;
          if (pinSet.has(node.id) && !(node.data as Record<string, unknown>).pinned) {
            nextNode = { ...nextNode, data: { ...nextNode.data, pinned: true } };
          }
          const validPosition = validMap.get(node.id);
          if (validPosition) {
            nextNode = {
              ...nextNode,
              data: { ...nextNode.data, lastValidPosition: validPosition },
            };
          }
          return nextNode;
        }),
      );
    },
    [onNodesChange, setNodes],
  );

  const refreshReportJob = useCallback(async (jobId: string) => {
    const snapshot = await getReportJob(jobId);
    setReportJobId(snapshot.job_id);
    setReportSections(buildSectionStates(snapshot.report_sections, snapshot.status));
    setIsGenerating(snapshot.status !== 'completed' && snapshot.status !== 'failed');
    setReportDone(snapshot.status === 'completed');
  }, []);

  const scheduleReportRefresh = useCallback(
    (jobId: string) => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = window.setTimeout(() => {
        void refreshReportJob(jobId);
      }, 120);
    },
    [refreshReportJob],
  );

  const reclusterEvidenceNodes = useCallback(() => {
    window.setTimeout(() => {
      setNodes((prev) => {
        const evidenceNodes = prev.filter(isEvidenceCanvasNode);
        cluster(evidenceNodes);
        return prev;
      });
    }, 100);
  }, [cluster, setNodes]);

  const handleFiles = useCallback(
    async (files: File[], position: { x: number; y: number }) => {
      let resolvedCaseId = caseId;

      if (!resolvedCaseId) {
        const response = await createCase({ title: DEFAULT_CASE_TITLE });
        resolvedCaseId = response.case_id;
        setCaseId(response.case_id);
        setCaseTitle(DEFAULT_CASE_TITLE);
      }

      if (!resolvedCaseId) {
        return;
      }

      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        const flowNodeId = `upload-${Date.now()}-${index}`;
        const filePosition = {
          x: position.x + index * 20 - files.length * 10,
          y: position.y + index * 20,
        };

        const uploadingNode: Node<EvidenceNodeData> = {
          id: flowNodeId,
          type: 'evidenceNode',
          position: filePosition,
          data: {
            evidenceId: flowNodeId,
            filename: file.name,
            evidenceType: 'other',
            summary: '',
            entities: [],
            entityCount: 0,
            factCount: 0,
            labels: [],
            nodeStatus: 'uploading',
            uploadProgress: 0,
            isIndexed: false,
            hasConnections: false,
          },
        };

        setNodes((prev) => [...prev.filter((node) => node.type !== 'insightBadge'), uploadingNode, ...prev.filter((node) => node.type === 'insightBadge')]);

        try {
          const response = await uploadFiles(resolvedCaseId, [file], (parsed: ParsedEvidence) => {
            setNodes(
              updateEvidenceNodeByFlowId(flowNodeId, (node) => ({
                ...node,
                data: {
                  ...node.data,
                  evidenceId: parsed.evidence_id,
                  filename: parsed.filename,
                  evidenceType: parsed.evidence_type,
                  summary: parsed.summary,
                  entities: parsed.entities,
                  entityCount: parsed.entity_count,
                  labels: parsed.labels,
                  nodeStatus: 'complete' as const,
                  uploadProgress: 100,
                  isIndexed: true,
                },
              })),
            );
            reclusterEvidenceNodes();
          });

          setAnalysisDone(false);
          setEdges([]);
          setNodes((prev) => prev.filter((node) => node.type !== 'insightBadge'));

          if (response.video_pending.length > 0) {
            const pending = response.video_pending[0];
            setNodes(
              updateEvidenceNodeByFlowId(flowNodeId, (node) => ({
                ...node,
                data: {
                  ...node.data,
                  evidenceId: pending.evidence_id ?? flowNodeId,
                  filename: pending.filename,
                  evidenceType: 'video',
                  summary: 'Video queued for analysis and reconstruction.',
                  nodeStatus: 'complete' as const,
                  uploadProgress: 100,
                  isIndexed: false,
                },
              })),
            );
            reclusterEvidenceNodes();
          }

          const failedUpload = response.parsed.find((item) => item.status === 'error');
          const hasSuccessfulParsedEvidence = response.parsed.some(
            (item) => item.status === 'parsed' && item.evidence_id,
          );

          if (!hasSuccessfulParsedEvidence && response.video_pending.length === 0) {
            setNodes(
              updateEvidenceNodeByFlowId(flowNodeId, (node) => ({
                ...node,
                data: {
                  ...node.data,
                  summary: failedUpload?.error || 'Unable to parse this evidence item.',
                  nodeStatus: 'complete' as const,
                  uploadProgress: 100,
                  isIndexed: false,
                },
              })),
            );
          }
        } catch {
          setNodes(
            updateEvidenceNodeByFlowId(flowNodeId, (node) => ({
              ...node,
              data: {
                ...node.data,
                summary: 'Upload failed. Please try again.',
                nodeStatus: 'complete' as const,
                uploadProgress: 100,
                isIndexed: false,
              },
            })),
          );
        }
      }
    },
    [caseId, reclusterEvidenceNodes, setEdges, setNodes],
  );

  const handleAddFilesFromButton = useCallback(
    (files: File[]) => {
      void handleFiles(files, { x: 0, y: 0 });
    },
    [handleFiles],
  );

  const { isDragOver, dropLabelPos, handlers: dropHandlers } = useFileDrop({
    onFiles: (files, position) => {
      void handleFiles(files, position);
    },
  });

  const handleAnalyze = useCallback(async () => {
    const evidenceNodes = nodesRef.current.filter(isEvidenceCanvasNode);
    if (evidenceNodes.length === 0 || isAnalyzing || !caseId) {
      return;
    }

    setIsAnalyzing(true);
    setNodes((prev) =>
      prev.map((node) =>
        node.type === 'evidenceNode'
          ? { ...node, data: { ...node.data, analyzing: true } }
          : node,
      ),
    );
    setShowAnalyzeWave(true);
    window.setTimeout(() => setShowAnalyzeWave(false), 1600);

    try {
      const result: AnalysisResponse = await analyzeCase(caseId);

      await new Promise<void>((resolve) => {
        setNodes((prev) => {
          const evidenceOnly = prev.filter(isEvidenceCanvasNode);
          cluster(evidenceOnly);
          return prev
            .filter((node) => node.type !== 'insightBadge')
            .map((node) =>
              node.type === 'evidenceNode'
                ? { ...node, data: { ...node.data, analyzing: false } }
                : node,
            );
        });
        window.setTimeout(resolve, 900);
      });

      setEdges([]);
      const freshEvidenceNodes = nodesRef.current.filter(isEvidenceCanvasNode);
      const newEdges = buildEdgesFromAnalysis(result, freshEvidenceNodes);
      await staggerEdgeReveal(newEdges, setEdges);

      if (result.contradictions.items.length > 0) {
        const badgePositionSource =
          nodesRef.current[Math.floor(nodesRef.current.length / 2)]?.position ?? { x: 200, y: 200 };
        setNodes((prev) => [
          ...prev.filter((node) => node.type !== 'insightBadge'),
          {
            id: 'insight-contradiction-count',
            type: 'insightBadge',
            position: { x: badgePositionSource.x + 80, y: badgePositionSource.y - 80 },
            data: {
              insightType: 'contradiction',
              text: `${result.contradictions.summary.total} contradiction${result.contradictions.summary.total > 1 ? 's' : ''} found`,
            },
            draggable: false,
            selectable: false,
          },
        ]);
      }

      setAnalysisDone(true);
    } finally {
      setIsAnalyzing(false);
      setNodes((prev) =>
        prev.map((node) =>
          node.type === 'evidenceNode'
            ? { ...node, data: { ...node.data, analyzing: false } }
            : node,
        ),
      );
    }
  }, [caseId, cluster, isAnalyzing, setEdges, setNodes]);

  const handleGenerateReport = useCallback(async () => {
    if (isGenerating || !caseId) {
      return;
    }

    setReportSidebarOpen(true);
    setIsGenerating(true);
    setReportDone(false);
    setReportJobId(null);
    setReportSections([]);

    try {
      const response = await generateReport(caseId);
      setReportJobId(response.job_id);
      await refreshReportJob(response.job_id);
      streamCleanupRef.current?.();
      streamCleanupRef.current = streamReport(
        response.job_id,
        () => {
          scheduleReportRefresh(response.job_id);
        },
        () => {
          scheduleReportRefresh(response.job_id);
        },
      );
    } catch {
      setIsGenerating(false);
    }
  }, [caseId, isGenerating, refreshReportJob, scheduleReportRefresh]);

  const handleResetLayout = useCallback(() => {
    if (USE_MOCK) {
      const resetNodes = buildInitialMockNodes();
      const resetEdges = buildInitialMockEdges(resetNodes);
      setNodes(resetNodes);
      setEdges(resetEdges);
    }
    window.setTimeout(() => fitView({ duration: 600, padding: 0.12 }), 50);
  }, [fitView, setEdges, setNodes]);

  return (
    <div
      ref={wrapperRef}
      style={{ width: '100%', height: '100%', display: 'flex' }}
      {...dropHandlers}
    >
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <div
          className={
            [isReclustering ? 'is-reclustering' : '', isSnappingBack ? 'is-snapping-back' : '']
              .filter(Boolean)
              .join(' ') || undefined
          }
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
            <Background variant={BackgroundVariant.Dots} gap={20} size={1.5} color="#E8E6E0" />

            <CanvasToolbar
              evidenceCount={evidenceCount}
              indexedEvidenceCount={indexedEvidenceCount}
              isAnalyzing={isAnalyzing}
              isGenerating={isGenerating}
              caseId={caseId}
              onAddFiles={handleAddFilesFromButton}
              onGenerateReport={handleGenerateReport}
            />

            <ZoomControls onReset={handleResetLayout} />
          </ReactFlow>
        </div>

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

        {showAnalyzeWave && <div className="canvas-analyze-wave" />}

        <div style={{ position: 'absolute', bottom: '24px', right: '24px', zIndex: 50, width: '80px' }}>
          <AgentOrb />
        </div>
      </div>

      {reportSidebarOpen && (
        <ReportProgressSidebar
          jobId={reportJobId}
          sections={reportSections}
          isGenerating={isGenerating}
          done={reportDone}
          caseId={caseId}
        />
      )}
    </div>
  );
}

interface EvidenceCanvasProps {
  caseId?: string;
  onWorkspaceChange?: (summary: WorkspaceSummary) => void;
}

export function EvidenceCanvas({
  caseId: _caseId,
  onWorkspaceChange,
}: EvidenceCanvasProps = {}) {
  return (
    <ReactFlowProvider>
      <EvidenceCanvasInner onWorkspaceChange={onWorkspaceChange} />
    </ReactFlowProvider>
  );
}
