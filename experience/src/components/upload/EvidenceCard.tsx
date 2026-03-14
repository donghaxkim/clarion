'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ParsedEvidence } from '@/lib/types';
import { EvidenceTypeBadge, InlineTag, getEvidenceColor } from '@/components/ui/Badge';

interface EvidenceCardProps {
  evidence: ParsedEvidence;
  index: number;
}

export function EvidenceCard({ evidence, index }: EvidenceCardProps) {
  const color = getEvidenceColor(evidence.evidence_type);

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08, ease: 'easeOut' }}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${color}`,
        borderRadius: '6px',
        padding: '14px 16px',
        marginBottom: '8px',
      }}
    >
      {/* Filename + type */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '6px', gap: '8px' }}>
        <span
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {evidence.filename}
        </span>
        <EvidenceTypeBadge type={evidence.evidence_type} />
      </div>

      {/* Summary */}
      <p
        style={{
          fontSize: '12px',
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
          marginBottom: '8px',
        }}
      >
        {evidence.summary}
      </p>

      {/* Labels */}
      {evidence.labels.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
          {evidence.labels.map((label) => (
            <InlineTag key={label}>{label}</InlineTag>
          ))}
        </div>
      )}

      {/* Entity count */}
      <span
        style={{
          fontSize: '11px',
          color: 'var(--text-tertiary)',
          fontFamily: 'DM Mono, monospace',
        }}
      >
        {evidence.entity_count} {evidence.entity_count === 1 ? 'entity' : 'entities'}
      </span>
    </motion.div>
  );
}
