'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, FileText, Users } from 'lucide-react';

import { EntityChip } from '@/components/analysis/EntityChip';
import { EntityPanel } from '@/components/entity/EntityPanel';
import { ReportBlock } from '@/components/report/ReportBlock';
import { SectionEditor } from '@/components/report/SectionEditor';
import { getEvidenceColor } from '@/components/ui/Badge';
import { getCase, getCaseReport, streamReport } from '@/lib/api';
import { CaseReportState, Entity, FullCase, ParsedEvidence, ReportSection } from '@/lib/types';

interface SectionState {
  section: ReportSection;
  text: string;
  streaming: boolean;
  complete: boolean;
}

function isPendingAnalysisStatus(status?: string | null) {
  return status === 'queued' || status === 'running' || status === 'stale';
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

export default function ReportPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [caseData, setCaseData] = useState<FullCase | null>(null);
  const [reportState, setReportState] = useState<CaseReportState | null>(null);
  const [sections, setSections] = useState<SectionState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSection, setEditingSection] = useState<ReportSection | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const applyReportState = useCallback((nextState: CaseReportState) => {
    setReportState(nextState);
    setSections(buildSectionStates(nextState.report_sections, nextState.status));
  }, []);

  const refreshCaseState = useCallback(async () => {
    const nextCase = await getCase(caseId);
    setCaseData(nextCase);
  }, [caseId]);

  const refreshReportState = useCallback(async () => {
    const nextState = await getCaseReport(caseId);
    applyReportState(nextState);
  }, [applyReportState, caseId]);

  const loadInitialData = useCallback(async () => {
    const [nextCase, nextReport] = await Promise.all([getCase(caseId), getCaseReport(caseId)]);
    setCaseData(nextCase);
    applyReportState(nextReport);
  }, [applyReportState, caseId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await loadInitialData();
        if (!cancelled) {
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Unable to load this report right now.',
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [loadInitialData]);

  useEffect(
    () => () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (!reportState?.job_id || reportState.status === 'completed' || reportState.status === 'failed') {
      return;
    }

    const jobId = reportState.job_id;
    return streamReport(
      jobId,
      () => {
        if (refreshTimerRef.current !== null) {
          window.clearTimeout(refreshTimerRef.current);
        }
        refreshTimerRef.current = window.setTimeout(() => {
          void Promise.all([refreshReportState(), refreshCaseState()]);
        }, 120);
      },
      () => {
        void Promise.all([refreshReportState(), refreshCaseState()]);
      },
    );
  }, [refreshCaseState, refreshReportState, reportState?.job_id, reportState?.status]);

  useEffect(() => {
    if (!isPendingAnalysisStatus(caseData?.analysis_status)) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshCaseState();
    }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [caseData?.analysis_status, refreshCaseState]);

  const handleSectionUpdated = useCallback(async (_response?: unknown) => {
    try {
      await refreshReportState();
      setError(null);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : 'Unable to refresh the updated report.',
      );
    }
  }, [refreshReportState]);

  const evidence: ParsedEvidence[] = caseData?.evidence ?? [];
  const entities: Entity[] = caseData?.report_relevant_entities ?? [];
  const contradictionCount = caseData?.contradictions.length ?? 0;
  const missingCount = caseData?.missing_info.length ?? 0;
  const analysisFailed = caseData?.analysis_status === 'failed';
  const analysisFailureMessage =
    caseData?.analysis_error || 'Case analysis is unavailable right now.';

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          height: '48px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          background: 'var(--bg-surface)',
          flexShrink: 0,
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <span style={{ fontSize: '13px', fontWeight: 600, letterSpacing: '0.12em', color: 'var(--text-primary)' }}>
          CLARION
        </span>
        <span style={{ marginLeft: '12px', fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'DM Mono, monospace' }}>
          / report
        </span>
        <div style={{ flex: 1 }} />
        <span
          style={{
            fontSize: '12px',
            color:
              reportState?.status === 'failed'
                ? 'var(--severity-high)'
                : reportState?.status === 'completed'
                  ? 'var(--severity-low)'
                  : 'var(--text-tertiary)',
          }}
        >
          {loading
            ? 'Loading...'
            : reportState?.status === 'completed'
              ? 'Complete'
              : reportState?.status === 'failed'
                ? 'Failed'
                : 'Generating...'}
        </span>
      </header>

      {error && (
        <div
          style={{
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)',
            padding: '10px 24px',
            fontSize: '12px',
            color: 'var(--severity-high)',
          }}
        >
          {error}
        </div>
      )}

      {analysisFailed && (
        <div
          style={{
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)',
            padding: '10px 24px',
            fontSize: '12px',
            color: 'var(--severity-med)',
          }}
        >
          {analysisFailureMessage}
        </div>
      )}

      <div style={{ flex: 1, display: 'flex', maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
        <aside
          style={{
            width: '240px',
            flexShrink: 0,
            borderRight: '1px solid var(--border)',
            padding: '20px 16px',
            overflowY: 'auto',
            position: 'sticky',
            top: '48px',
            height: 'calc(100vh - 48px)',
          }}
        >
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <FileText size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Evidence
              </span>
            </div>
            {evidence.map((item) => (
              <div
                key={item.evidence_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 0',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                <div
                  style={{
                    width: '3px',
                    height: '14px',
                    background: getEvidenceColor(item.evidence_type),
                    borderRadius: '1px',
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                  }}
                  title={item.filename}
                >
                  {item.filename}
                </span>
              </div>
            ))}
          </div>

          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <Users size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Entities
              </span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {entities.slice(0, 8).map((entity) => (
                <EntityChip key={entity.id} entity={entity} onClick={(nextEntity) => setSelectedEntity(nextEntity)} />
              ))}
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <AlertTriangle size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Issues
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {analysisFailed && (
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--severity-med)',
                    background: 'var(--severity-med-bg)',
                    padding: '4px 8px',
                    borderRadius: '4px',
                  }}
                >
                  Analysis unavailable
                </div>
              )}
              {contradictionCount > 0 && (
                <div style={{ fontSize: '12px', color: 'var(--severity-high)', background: 'var(--severity-high-bg)', padding: '4px 8px', borderRadius: '4px' }}>
                  {contradictionCount} contradiction{contradictionCount !== 1 ? 's' : ''}
                </div>
              )}
              {missingCount > 0 && (
                <div style={{ fontSize: '12px', color: 'var(--severity-med)', background: 'var(--severity-med-bg)', padding: '4px 8px', borderRadius: '4px' }}>
                  {missingCount} evidence gap{missingCount !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          </div>
        </aside>

        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '48px 64px',
            maxWidth: '720px',
            margin: '0 auto',
          }}
        >
          <AnimatePresence>
            {sections.map((item) => (
              <motion.div
                key={item.section.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
                style={{ position: 'relative' }}
              >
                <ReportBlock
                  section={item.section}
                  streamingText={item.text}
                  isStreaming={item.streaming}
                  onEdit={(section) => setEditingSection(section)}
                />
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && sections.length === 0 && (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', fontStyle: 'italic' }}>
              Loading report...
            </p>
          )}

          {!loading && sections.length === 0 && !error && (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', fontStyle: 'italic' }}>
              Report generation has started, but no sections are ready yet.
            </p>
          )}

          {!loading && <div style={{ height: '80px' }} />}
        </main>

        <div style={{ width: '48px', flexShrink: 0 }} />
      </div>

      {editingSection && (
        <SectionEditor
          section={editingSection}
          caseId={caseId}
          onClose={() => setEditingSection(null)}
          onUpdated={handleSectionUpdated}
        />
      )}

      {selectedEntity && (
        <EntityPanel
          entity={selectedEntity}
          caseId={caseId}
          analysisStatus={caseData?.analysis_status}
          analysisError={caseData?.analysis_error}
          onClose={() => setSelectedEntity(null)}
        />
      )}
    </div>
  );
}
