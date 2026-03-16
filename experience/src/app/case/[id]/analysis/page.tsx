'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowRight, CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';

import { ContradictionCard } from '@/components/analysis/ContradictionCard';
import { EntityChip } from '@/components/analysis/EntityChip';
import { MissingInfoCard } from '@/components/analysis/MissingInfoCard';
import { ThreadLines } from '@/components/analysis/ThreadLines';
import { EntityPanel } from '@/components/entity/EntityPanel';
import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { analyzeCase, generateReport } from '@/lib/api';
import { AnalysisResponse, Entity } from '@/lib/types';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: index * 0.05, duration: 0.3, ease: 'easeOut' },
  }),
};

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [threadActive, setThreadActive] = useState(false);

  const cardRefs = useRef<React.RefObject<HTMLDivElement>[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await analyzeCase(caseId);
        if (!cancelled) {
          setAnalysis(data);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to analyze this case.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          window.setTimeout(() => setThreadActive(true), 600);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useEffect(() => {
    if (!analysis) {
      return;
    }
    cardRefs.current = analysis.contradictions.items.map(() => React.createRef<HTMLDivElement>());
  }, [analysis]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);

    try {
      await generateReport(caseId);
      router.push(`/case/${caseId}/report`);
    } catch (generateError) {
      setGenerating(false);
      setError(
        generateError instanceof Error
          ? generateError.message
          : 'Unable to start report generation.',
      );
    }
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <Header />
        <ProgressBar />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>Analyzing evidence...</p>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, padding: '24px' }}>
          <p style={{ color: 'var(--severity-high)', fontSize: '13px', maxWidth: '480px', textAlign: 'center' }}>
            {error ?? 'Analysis data is unavailable for this case.'}
          </p>
        </div>
      </div>
    );
  }

  const {
    contradictions,
    missing_info,
    entities,
    dimensions_discovered,
    total_facts_indexed,
    total_entities,
    case_type_detected,
  } = analysis;

  const flatRefs = cardRefs.current as React.RefObject<HTMLElement>[];

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <Header />

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
            {dimensions_discovered.map((dimension) => (
              <span
                key={dimension.name}
                style={{
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  padding: '2px 8px',
                  borderRadius: '3px',
                }}
              >
                {dimension.name}
              </span>
            ))}
          </div>
        </div>
      </motion.div>

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
              {(contradictions.summary.high > 0 || contradictions.summary.medium > 0) &&
                contradictions.summary.low > 0 &&
                ' · '}
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
            contradictions.items.map((contradiction, index) => (
              <motion.div key={contradiction.id} custom={index} initial="hidden" animate="show" variants={fadeUp}>
                <ContradictionCard
                  ref={cardRefs.current[index]}
                  contradiction={contradiction}
                  index={index}
                />
              </motion.div>
            ))
          )}
        </div>

        <div style={{ flex: '0 0 45%', display: 'flex', flexDirection: 'column' }}>
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
              {entities.map((entity, index) => (
                <motion.div key={entity.id} custom={index} initial="hidden" animate="show" variants={fadeUp}>
                  <EntityChip entity={entity} onClick={(nextEntity) => setSelectedEntity(nextEntity)} />
                </motion.div>
              ))}
            </div>
          </div>

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
            {missing_info.items.map((item, index) => (
              <motion.div key={item.id} custom={index} initial="hidden" animate="show" variants={fadeUp}>
                <MissingInfoCard item={item} />
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <div
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          padding: '12px 24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: '8px',
        }}
      >
        {error && (
          <p style={{ fontSize: '12px', color: 'var(--severity-high)', margin: 0 }}>{error}</p>
        )}
        <Button variant="primary" size="lg" onClick={handleGenerate} disabled={generating}>
          {generating ? 'Generating...' : 'Generate Report'}
          {!generating && <ArrowRight size={14} strokeWidth={2} />}
        </Button>
      </div>

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

function Header() {
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
