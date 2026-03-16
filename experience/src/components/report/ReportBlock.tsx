'use client';

import React, { useState } from 'react';
import { Pencil } from 'lucide-react';
import { ReportSection, Citation } from '@/lib/types';
import { StreamingText } from './StreamingText';
import { CitationTooltip } from './CitationTooltip';
import { TimelineBlock } from './TimelineBlock';

interface ReportBlockProps {
  section: ReportSection;
  streamingText?: string;
  isStreaming?: boolean;
  onEdit?: (section: ReportSection) => void;
}

function renderTextWithCitations(text: string, citations: Citation[]) {
  if (!citations || citations.length === 0) {
    return <span>{text}</span>;
  }

  // Simple approach: render citation markers inline as superscripts
  // Parse [1], [2] etc. markers placed in the text
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10) - 1;
          const citation = citations[idx];
          if (citation) {
            return <CitationTooltip key={i} citation={citation} index={idx} />;
          }
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

export function ReportBlock({ section, streamingText, isStreaming, onEdit }: ReportBlockProps) {
  const [hovered, setHovered] = useState(false);
  const displayText = isStreaming !== undefined ? (streamingText || '') : (section.text || '');
  const activelyStreaming = isStreaming === true;

  const wrapperStyle: React.CSSProperties = {
    position: 'relative',
    marginBottom: '24px',
  };

  const pencilStyle: React.CSSProperties = {
    position: 'absolute',
    right: '-28px',
    top: '2px',
    opacity: hovered && onEdit ? 1 : 0,
    transition: 'opacity 200ms',
    cursor: 'pointer',
    color: 'var(--text-tertiary)',
    background: 'none',
    border: 'none',
    padding: '4px',
    display: 'flex',
  };

  function handleEdit() {
    if (onEdit) onEdit(section);
  }

  // HEADING
  if (section.block_type === 'heading') {
    const level = section.heading_level || 2;
    const sizes = { 1: '26px', 2: '20px', 3: '16px' };
    const margins = { 1: '0 0 24px', 2: '32px 0 16px', 3: '24px 0 12px' };
    return (
      <div
        style={{ ...wrapperStyle, margin: margins[level as 1 | 2 | 3] }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div
          style={{
            fontFamily: 'Newsreader, serif',
            fontStyle: 'italic',
            fontWeight: 500,
            fontSize: sizes[level as 1 | 2 | 3],
            color: 'var(--text-primary)',
            lineHeight: 1.3,
          }}
        >
          {section.text}
        </div>
        {onEdit && (
          <button style={pencilStyle} onClick={handleEdit} aria-label="Edit section">
            <Pencil size={13} strokeWidth={1.5} />
          </button>
        )}
      </div>
    );
  }

  // TIMELINE
  if (section.block_type === 'timeline' && section.timeline_events) {
    return (
      <div style={{ ...wrapperStyle, margin: '24px 0' }}>
        <TimelineBlock events={section.timeline_events} />
      </div>
    );
  }

  // COUNTER ARGUMENT
  if (section.block_type === 'counter_argument') {
    return (
      <div
        style={{
          ...wrapperStyle,
          background: 'var(--severity-high-bg)',
          borderTop: '2px solid var(--severity-high)',
          borderRadius: '0 0 6px 6px',
          padding: '16px 20px',
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <p
          style={{
            fontSize: '11px',
            fontWeight: 600,
            letterSpacing: '0.08em',
            color: 'var(--severity-high)',
            textTransform: 'uppercase',
            marginBottom: '8px',
            fontStyle: 'italic',
            fontFamily: 'Newsreader, serif',
          }}
        >
          Opposing Perspective
        </p>
        <p
          className="report-text"
          style={{ color: 'var(--text-primary)', fontFamily: 'Newsreader, serif', fontSize: '15px', lineHeight: 1.7 }}
        >
          {displayText}
          {activelyStreaming && <span className="streaming-cursor" />}
        </p>
        {onEdit && (
          <button style={{ ...pencilStyle, right: '8px', top: '8px' }} onClick={handleEdit}>
            <Pencil size={13} strokeWidth={1.5} />
          </button>
        )}
      </div>
    );
  }

  // IMAGE / EVIDENCE_IMAGE
  if (section.block_type === 'image' || section.block_type === 'evidence_image') {
    return (
      <div style={{ ...wrapperStyle }}>
        {section.media ? (
          <img
            src={section.media}
            alt=""
            style={{ width: '100%', borderRadius: '6px', display: 'block' }}
          />
        ) : (
          <div
            style={{
              width: '100%',
              height: '200px',
              background: 'var(--bg-elevated)',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>[Image: {section.id}]</span>
          </div>
        )}
      </div>
    );
  }

  if (section.block_type === 'video') {
    return (
      <div style={{ ...wrapperStyle }}>
        {section.media ? (
          <video
            controls
            src={section.media}
            style={{ width: '100%', borderRadius: '6px', display: 'block' }}
          />
        ) : (
          <div
            style={{
              width: '100%',
              height: '220px',
              background: 'var(--bg-elevated)',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>[Video: {section.id}]</span>
          </div>
        )}
      </div>
    );
  }

  // DEFAULT: TEXT
  return (
    <div
      style={wrapperStyle}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <p
        style={{
          fontFamily: 'Newsreader, serif',
          fontSize: '16px',
          lineHeight: 1.8,
          color: 'var(--text-primary)',
          margin: 0,
        }}
      >
        {activelyStreaming ? (
          <>
            {displayText}
            <span className="streaming-cursor" />
          </>
        ) : (
          renderTextWithCitations(section.text || '', section.citations || [])
        )}
      </p>
      {onEdit && (
        <button style={pencilStyle} onClick={handleEdit} aria-label="Edit section">
          <Pencil size={13} strokeWidth={1.5} />
        </button>
      )}
    </div>
  );
}
