'use client';

import React, { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ReportSection } from '@/lib/types';

export interface SectionState {
  section: ReportSection;
  text: string;
  streaming: boolean;
  complete: boolean;
}

interface TocEntry {
  title: string;
  subtitle: string;
  description: string;
  status: 'pending' | 'streaming' | 'done';
}

interface ReportProgressSidebarProps {
  sections: SectionState[];
  isGenerating: boolean;
  done: boolean;
  caseId: string | null;
}

export function ReportProgressSidebar({
  sections,
  isGenerating,
  done,
  caseId,
}: ReportProgressSidebarProps) {
  const router = useRouter();

  const tocEntries = useMemo<TocEntry[]>(() => {
    const entries: TocEntry[] = [];
    let current: TocEntry | null = null;

    for (const s of sections) {
      if (s.section.block_type === 'heading' && s.section.heading_level === 2) {
        if (current) entries.push(current);
        current = {
          title: s.section.text ?? '',
          subtitle: '',
          description: '',
          status: s.streaming ? 'streaming' : s.complete ? 'done' : 'pending',
        };
      } else if (current) {
        // Update status: any child streaming → parent streaming
        if (s.streaming) current.status = 'streaming';
        else if (s.complete && current.status !== 'streaming') current.status = 'done';

        const bt = s.section.block_type;

        // Set subtitle based on content type being generated
        if (!current.subtitle) {
          if (bt === 'image' || bt === 'evidence_image') {
            current.subtitle = 'Generating image';
          } else if (bt === 'video') {
            current.subtitle = 'Generating video';
          } else if (bt === 'timeline') {
            current.subtitle = 'Building timeline';
          } else if (bt === 'counter_argument') {
            current.subtitle = 'Analyzing counter-arguments';
          } else if (bt === 'text') {
            current.subtitle = 'Writing analysis';
          }
        }

        // Grab first text block as description
        if (bt === 'text' && !current.description) {
          const raw = s.text || s.section.text || '';
          const clean = raw.replace(/\[\d+\]/g, '').trim();
          current.description = clean.slice(0, 90) + (clean.length > 90 ? '…' : '');
        }
      }
    }
    if (current) entries.push(current);
    return entries;
  }, [sections]);

  return (
    <div
      style={{
        width: '272px',
        flexShrink: 0,
        borderLeft: '1px solid var(--border)',
        background: 'var(--bg-surface)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: 'DM Sans, sans-serif',
      }}
    >
      {/* Header */}
      <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          {isGenerating ? (
            <>
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  display: 'inline-block',
                  animation: 'sidebarDotPulse 1.2s ease-in-out infinite',
                  flexShrink: 0,
                }}
              />
              <style>{`
                @keyframes sidebarDotPulse {
                  0%, 100% { opacity: 1; transform: scale(1); }
                  50% { opacity: 0.4; transform: scale(0.8); }
                }
                @keyframes sidebarEntryDot {
                  0%, 100% { opacity: 1; }
                  50% { opacity: 0.3; }
                }
              `}</style>
            </>
          ) : (
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: '#6B9B7E',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
          )}
          <span
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--text-primary)',
              letterSpacing: '-0.01em',
            }}
          >
            {isGenerating ? 'Agents are at work' : 'Report complete'}
          </span>
        </div>
        <p
          style={{
            margin: 0,
            fontSize: '11px',
            color: 'var(--text-tertiary)',
            lineHeight: 1.4,
          }}
        >
          {isGenerating
            ? 'Generating your litigation report…'
            : 'All sections have been generated.'}
        </p>
      </div>

      {/* TOC label */}
      <div
        style={{
          padding: '10px 16px 6px',
          fontSize: '10px',
          fontFamily: 'DM Mono, monospace',
          fontWeight: 500,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
        }}
      >
        Contents
      </div>

      {/* TOC entries */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 0 8px' }}>
        {tocEntries.length === 0 && isGenerating && (
          <div
            style={{
              padding: '12px 16px',
              fontSize: '12px',
              color: 'var(--text-tertiary)',
            }}
          >
            Starting…
          </div>
        )}
        {tocEntries.map((entry, i) => (
          <div
            key={i}
            style={{
              padding: '8px 16px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
              {/* Status dot */}
              <div style={{ paddingTop: '3px', flexShrink: 0 }}>
                {entry.status === 'streaming' ? (
                  <span
                    style={{
                      display: 'inline-block',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: 'var(--accent)',
                      animation: 'sidebarEntryDot 1s ease-in-out infinite',
                    }}
                  />
                ) : entry.status === 'done' ? (
                  <span
                    style={{
                      display: 'inline-block',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: '#6B9B7E',
                    }}
                  />
                ) : (
                  <span
                    style={{
                      display: 'inline-block',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: 'var(--border)',
                    }}
                  />
                )}
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 500,
                    color: entry.status === 'pending' ? 'var(--text-tertiary)' : 'var(--text-primary)',
                    lineHeight: 1.3,
                    marginBottom: (entry.subtitle || entry.description) ? '3px' : 0,
                  }}
                >
                  {entry.title}
                </div>
                {entry.subtitle && (
                  <div
                    style={{
                      fontSize: '11px',
                      fontWeight: 500,
                      color: entry.status === 'streaming' ? 'var(--accent)' : 'var(--text-secondary)',
                      lineHeight: 1.3,
                      marginBottom: entry.description ? '2px' : 0,
                    }}
                  >
                    {entry.subtitle}{entry.status === 'streaming' ? '…' : ''}
                  </div>
                )}
                {entry.description && (
                  <div
                    style={{
                      fontSize: '11px',
                      color: 'var(--text-tertiary)',
                      lineHeight: 1.4,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {entry.description}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* View Full Report button */}
      {done && (
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
          <button
            onClick={() => caseId && router.push(`/case/${caseId}/report`)}
            style={{
              width: '100%',
              padding: '9px 0',
              background: 'var(--accent)',
              border: 'none',
              borderRadius: '6px',
              fontFamily: 'DM Sans, sans-serif',
              fontSize: '13px',
              fontWeight: 600,
              color: '#fff',
              cursor: 'pointer',
              letterSpacing: '-0.01em',
            }}
          >
            View Full Report
          </button>
        </div>
      )}
    </div>
  );
}
