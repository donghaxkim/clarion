'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Users, AlertTriangle } from 'lucide-react';

import { ReportBlock } from '@/components/report/ReportBlock';
import { SectionEditor } from '@/components/report/SectionEditor';
import { EntityChip } from '@/components/analysis/EntityChip';
import { EntityPanel } from '@/components/entity/EntityPanel';
import { EvidenceTypeBadge, getEvidenceColor } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';

import { ReportSection, Entity, ParsedEvidence } from '@/lib/types';
import { streamReport, getCase } from '@/lib/api';
import { MOCK_FULL_CASE, MOCK_REPORT_SECTIONS } from '@/lib/mock-data';

interface SectionState {
  section: ReportSection;
  text: string;
  streaming: boolean;
  complete: boolean;
}

export default function ReportPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [sections, setSections] = useState<SectionState[]>([]);
  const [progress, setProgress] = useState<number | undefined>(undefined);
  const [done, setDone] = useState(false);
  const [evidence, setEvidence] = useState<ParsedEvidence[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [contradictionCount, setContradictionCount] = useState(0);
  const [missingCount, setMissingCount] = useState(0);
  const [editingSection, setEditingSection] = useState<ReportSection | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // Load sidebar data
  useEffect(() => {
    async function loadCase() {
      try {
        const c = await getCase(caseId);
        setEvidence(c.evidence);
        setEntities(c.entities);
        setContradictionCount(c.contradictions.length);
        setMissingCount(c.missing_info.length);
      } catch {
        const c = MOCK_FULL_CASE;
        setEvidence(c.evidence);
        setEntities(c.entities);
        setContradictionCount(c.contradictions.length);
        setMissingCount(c.missing_info.length);
      }
    }
    loadCase();
  }, [caseId]);

  // Start streaming
  useEffect(() => {
    const cleanup = streamReport(
      caseId,
      (event) => {
        if (event.event === 'section_start') {
          setSections((prev) => [
            ...prev,
            { section: event.section, text: '', streaming: true, complete: false },
          ]);
        } else if (event.event === 'section_delta') {
          setSections((prev) =>
            prev.map((s) =>
              s.section.id === event.section_id
                ? { ...s, text: s.text + event.delta_text, streaming: true }
                : s
            )
          );
          // Auto-scroll
          setTimeout(() => {
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
          }, 50);
        } else if (event.event === 'section_complete') {
          setSections((prev) =>
            prev.map((s) =>
              s.section.id === event.section_id
                ? { ...s, streaming: false, complete: true }
                : s
            )
          );
        } else if (event.event === 'status') {
          setProgress(event.progress);
        } else if (event.event === 'done') {
          setDone(true);
          setProgress(100);
        }
      },
      () => {
        // On error, load mock sections
        const mockStates: SectionState[] = MOCK_REPORT_SECTIONS.map((s) => ({
          section: s,
          text: s.text || '',
          streaming: false,
          complete: true,
        }));
        setSections(mockStates);
        setDone(true);
        setProgress(100);
      }
    );
    cleanupRef.current = cleanup;
    return () => cleanup();
  }, [caseId]);

  function handleSectionUpdated(sectionId: string) {
    setSections((prev) =>
      prev.map((s) =>
        s.section.id === sectionId ? { ...s, streaming: false, complete: true } : s
      )
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      {/* Top bar */}
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
        {!done && (
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Generating...
          </span>
        )}
        {done && (
          <span style={{ fontSize: '12px', color: 'var(--severity-low)' }}>
            Complete
          </span>
        )}
      </header>

      {/* Progress */}
      {!done && <ProgressBar progress={progress} />}

      {/* Three-column layout */}
      <div style={{ flex: 1, display: 'flex', maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
        {/* Left sidebar: Evidence + Entities + Issues */}
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
          {/* Evidence */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <FileText size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Evidence
              </span>
            </div>
            {evidence.map((ev) => (
              <div
                key={ev.evidence_id}
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
                    background: getEvidenceColor(ev.evidence_type),
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
                  title={ev.filename}
                >
                  {ev.filename}
                </span>
              </div>
            ))}
          </div>

          {/* Entities */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <Users size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Entities
              </span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {entities.slice(0, 8).map((entity) => (
                <EntityChip
                  key={entity.id}
                  entity={entity}
                  onClick={(e) => setSelectedEntity(e)}
                />
              ))}
            </div>
          </div>

          {/* Issues */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <AlertTriangle size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
              <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                Issues
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
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

        {/* Center: Report document */}
        <main
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '48px 64px',
            maxWidth: '720px',
            margin: '0 auto',
          }}
        >
          <AnimatePresence>
            {sections.map((s, i) => (
              <motion.div
                key={s.section.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
                style={{ position: 'relative' }}
              >
                <ReportBlock
                  section={s.section}
                  streamingText={s.text}
                  isStreaming={s.streaming}
                  onEdit={done ? (section) => setEditingSection(section) : undefined}
                />
              </motion.div>
            ))}
          </AnimatePresence>

          {!done && sections.length === 0 && (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', fontStyle: 'italic' }}>
              Generating your report...
            </p>
          )}

          {done && <div style={{ height: '80px' }} />}
        </main>

        {/* Right: empty gutter (for pencil icons) */}
        <div style={{ width: '48px', flexShrink: 0 }} />
      </div>

      {/* Section editor panel */}
      {editingSection && (
        <SectionEditor
          section={editingSection}
          caseId={caseId}
          onClose={() => setEditingSection(null)}
          onUpdated={handleSectionUpdated}
        />
      )}

      {/* Entity panel */}
      {selectedEntity && (
        <EntityPanel
          entity={selectedEntity}
          caseId={caseId}
          onClose={() => setSelectedEntity(null)}
        />
      )}
    </div>
  );
}
