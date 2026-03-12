'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { Entity, EntityDetailResponse } from '@/lib/types';
import { getEntityDetail } from '@/lib/api';
import { EntityTypeDot } from '@/components/ui/Badge';
import { SeverityBadge } from '@/components/ui/SeverityBadge';

interface EntityPanelProps {
  entity: Entity;
  caseId: string;
  onClose: () => void;
}

export function EntityPanel({ entity, caseId, onClose }: EntityPanelProps) {
  const [detail, setDetail] = useState<EntityDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getEntityDetail(caseId, entity.name);
        setDetail(data);
      } catch {
        setDetail({ entity, facts: [], contradictions: [] });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [entity, caseId]);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        key="backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(26,26,26,0.15)',
          zIndex: 40,
        }}
      />

      {/* Panel */}
      <motion.div
        key="panel"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'tween', duration: 0.25, ease: 'easeOut' }}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '400px',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <EntityTypeDot type={entity.type} />
            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {entity.name}
            </span>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 500,
                letterSpacing: '0.06em',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
                background: 'var(--bg-elevated)',
                padding: '1px 6px',
                borderRadius: '3px',
              }}
            >
              {entity.type}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-tertiary)',
              display: 'flex',
              padding: '4px',
              borderRadius: '4px',
            }}
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {loading ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>Loading...</p>
          ) : detail ? (
            <>
              {/* Facts */}
              {detail.facts.length > 0 && (
                <section style={{ marginBottom: '24px' }}>
                  <h3
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      letterSpacing: '0.08em',
                      color: 'var(--text-tertiary)',
                      textTransform: 'uppercase',
                      marginBottom: '12px',
                    }}
                  >
                    Facts
                  </h3>
                  {detail.facts.map((fact, i) => (
                    <div
                      key={i}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        paddingBottom: '12px',
                        marginBottom: '12px',
                      }}
                    >
                      <p style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: '6px' }}>
                        {fact.fact}
                      </p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span
                          style={{
                            fontSize: '10px',
                            color: 'var(--accent)',
                            background: 'var(--accent-light)',
                            padding: '1px 6px',
                            borderRadius: '3px',
                            fontWeight: 500,
                          }}
                        >
                          {fact.dimension}
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            color: 'var(--text-tertiary)',
                            fontFamily: 'DM Mono, monospace',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {fact.excerpt}
                        </span>
                      </div>
                      {/* Reliability bar */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', width: '64px' }}>
                          Reliability
                        </span>
                        <div
                          style={{
                            flex: 1,
                            height: '2px',
                            background: 'var(--border)',
                            borderRadius: '1px',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              height: '100%',
                              width: `${fact.reliability * 100}%`,
                              background: `hsl(${fact.reliability * 120}, 50%, 50%)`,
                              borderRadius: '1px',
                              transition: 'width 600ms ease',
                            }}
                          />
                        </div>
                        <span
                          style={{
                            fontSize: '10px',
                            color: 'var(--text-tertiary)',
                            fontFamily: 'DM Mono, monospace',
                            width: '28px',
                            textAlign: 'right',
                          }}
                        >
                          {Math.round(fact.reliability * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </section>
              )}

              {/* Contradictions */}
              {detail.contradictions.length > 0 && (
                <section>
                  <h3
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      letterSpacing: '0.08em',
                      color: 'var(--text-tertiary)',
                      textTransform: 'uppercase',
                      marginBottom: '12px',
                    }}
                  >
                    Contradictions
                  </h3>
                  {detail.contradictions.map((c) => (
                    <div
                      key={c.id}
                      style={{
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        padding: '10px 12px',
                        marginBottom: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '6px' }}>
                        <SeverityBadge severity={c.severity} compact />
                        <p style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: 1.4, flex: 1 }}>
                          {c.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </section>
              )}

              {detail.facts.length === 0 && detail.contradictions.length === 0 && (
                <p style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>
                  No detailed information available for this entity.
                </p>
              )}
            </>
          ) : null}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
