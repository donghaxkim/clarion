'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowRight, CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';

import { ContradictionCard } from '@/components/analysis/ContradictionCard';
import { MissingInfoCard } from '@/components/analysis/MissingInfoCard';
import { EntityChip } from '@/components/analysis/EntityChip';
import { ThreadLines } from '@/components/analysis/ThreadLines';
import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { EntityPanel } from '@/components/entity/EntityPanel';

import { Entity, AnalysisResponse } from '@/lib/types';
import { analyzeCase, generateReport } from '@/lib/api';
import { MOCK_ANALYSIS, MOCK_CASE_ID } from '@/lib/mock-data';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.3, ease: 'easeOut' } }),
};

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [threadActive, setThreadActive] = useState(false);

  // Refs for thread animation — one per contradiction card
  const cardRefs = useRef<React.RefObject<HTMLDivElement>[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await analyzeCase(caseId);
        setAnalysis(data);
      } catch {
        setAnalysis(MOCK_ANALYSIS);
      } finally {
        setLoading(false);
        // Trigger thread animation after cards render
        setTimeout(() => setThreadActive(true), 600);
      }
    }
    load();
  }, [caseId]);

  // Build card refs when analysis loads
  useEffect(() => {
    if (!analysis) return;
    cardRefs.current = analysis.contradictions.items.map(() => React.createRef<HTMLDivElement>());
  }, [analysis]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      await generateReport(caseId);
      router.push(`/case/${caseId}/report`);
    } catch {
      router.push(`/case/${caseId}/report`);
    }
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <Header caseId={caseId} />
        <ProgressBar />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>Analyzing evidence...</p>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const { contradictions, missing_info, entities, dimensions_discovered, total_facts_indexed, total_entities, case_type_detected } = analysis;

  // Flatten card refs for thread lines (pair-wise: card A_fact and card B_fact elements)
  const flatRefs = cardRefs.current as React.RefObject<HTMLElement>[];

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <Header caseId={caseId} />

      {/* Summary bar */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
        style={{
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          padding: '16px 24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', marginBottom: '10px' }}>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: 'var(--accent)',
                background: 'var(--accent-light)',
                padding: '2px 8px',
                borderRadius: '3px',
              }}
            >
              {case_type_detected.toUpperCase()}
            </span>
            <StatBox label="facts indexed" value={total_facts_indexed} />
            <StatBox label="entities" value={total_entities} />
            <StatBox
              label="contradictions"
              value={contradictions.summary.total}
              accent={contradictions.summary.total > 0}
            />
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {dimensions_discovered.map((d) => (
              <span
                key={d.name}
                style={{
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  padding: '2px 8px',
                  borderRadius: '3px',
                }}
              >
                {d.name}
              </span>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Main two-column */}
      <div
        style={{
          flex: 1,
          maxWidth: '1280px',
          margin: '0 auto',
          width: '100%',
          display: 'flex',
          gap: 0,
        }}
      >
        {/* Left: Contradictions (55%) */}
        <div
          ref={containerRef}
          style={{
            flex: '0 0 55%',
            borderRight: '1px solid var(--border)',
            padding: '20px 24px',
            overflowY: 'auto',
            position: 'relative',
          }}
        >
          <ThreadLines
            sourceRefs={flatRefs}
            containerRef={containerRef as React.RefObject<HTMLElement>}
            active={threadActive && flatRefs.length > 1}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Contradictions
            </h2>
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
              {contradictions.summary.high > 0 && (
                <span style={{ color: 'var(--severity-high)' }}>{contradictions.summary.high} high</span>
              )}
              {contradictions.summary.high > 0 && contradictions.summary.medium > 0 && ' · '}
              {contradictions.summary.medium > 0 && (
                <span style={{ color: 'var(--severity-med)' }}>{contradictions.summary.medium} medium</span>
              )}
              {(contradictions.summary.high > 0 || contradictions.summary.medium > 0) && contradictions.summary.low > 0 && ' · '}
              {contradictions.summary.low > 0 && (
                <span style={{ color: 'var(--severity-low)' }}>{contradictions.summary.low} low</span>
              )}
            </span>
          </div>

          {contradictions.items.length === 0 ? (
            <div
              style={{
                background: 'var(--severity-low-bg)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: 'var(--severity-low)',
                fontSize: '13px',
              }}
            >
              <CheckCircle size={16} strokeWidth={1.5} />
              No contradictions found
            </div>
          ) : (
            contradictions.items.map((c, i) => (
              <motion.div key={c.id} custom={i} initial="hidden" animate="show" variants={fadeUp}>
                <ContradictionCard
                  ref={cardRefs.current[i]}
                  contradiction={c}
                  index={i}
                />
              </motion.div>
            ))
          )}
        </div>

        {/* Right: Entities + Gaps (45%) */}
        <div style={{ flex: '0 0 45%', display: 'flex', flexDirection: 'column' }}>
          {/* Entities */}
          <div
            style={{
              flex: '0 0 50%',
              borderBottom: '1px solid var(--border)',
              padding: '20px 24px',
              overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Entities</h2>
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--text-tertiary)',
                  fontFamily: 'DM Mono, monospace',
                }}
              >
                {entities.length}
              </span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {entities.map((entity, i) => (
                <motion.div key={entity.id} custom={i} initial="hidden" animate="show" variants={fadeUp}>
                  <EntityChip
                    entity={entity}
                    onClick={(e) => setSelectedEntity(e)}
                  />
                </motion.div>
              ))}
            </div>
          </div>

          {/* Evidence Gaps */}
          <div style={{ flex: '0 0 50%', padding: '20px 24px', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Evidence Gaps</h2>
              {missing_info.critical > 0 && (
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    color: 'var(--severity-high)',
                    background: 'var(--severity-high-bg)',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    letterSpacing: '0.04em',
                  }}
                >
                  {missing_info.critical} CRITICAL
                </span>
              )}
            </div>
            {missing_info.items.map((item, i) => (
              <motion.div key={item.id} custom={i} initial="hidden" animate="show" variants={fadeUp}>
                <MissingInfoCard item={item} />
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'flex-end',
        }}
      >
        <Button variant="primary" size="lg" onClick={handleGenerate} disabled={generating}>
          {generating ? 'Generating...' : 'Generate Report'}
          {!generating && <ArrowRight size={14} strokeWidth={2} />}
        </Button>
      </div>

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

function Header({ caseId }: { caseId: string }) {
  return (
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
      <span
        style={{
          fontSize: '13px',
          fontWeight: 600,
          letterSpacing: '0.12em',
          color: 'var(--text-primary)',
        }}
      >
        CLARION
      </span>
      <span
        style={{
          marginLeft: '12px',
          fontSize: '12px',
          color: 'var(--text-tertiary)',
          fontFamily: 'DM Mono, monospace',
        }}
      >
        / intelligence
      </span>
    </header>
  );
}

function StatBox({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
      <span
        style={{
          fontSize: '18px',
          fontWeight: 600,
          color: accent ? 'var(--severity-high)' : 'var(--text-primary)',
          fontFamily: 'DM Mono, monospace',
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>{label}</span>
    </div>
  );
}
