'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { ReportSection } from '@/lib/types';

export interface SectionState {
  section: ReportSection;
  text: string;
  streaming: boolean;
  complete: boolean;
}

interface TocEntry {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  status: 'pending' | 'streaming' | 'done';
}

interface ReportProgressSidebarProps {
  jobId: string | null;
  sections: SectionState[];
  isGenerating: boolean;
  done: boolean;
  caseId: string | null;
}

interface TypingProgress {
  id: string;
  targetDescription: string;
  lastTickAt: number;
  snapshotStartedAt: number;
  carry: number;
}

const TYPEWRITER_TICK_MS = 33;
const TYPEWRITER_BURST_CHARS_PER_SECOND = 50;
const TYPEWRITER_STEADY_CHARS_PER_SECOND = 20;
const TYPEWRITER_BURST_DURATION_MS = 500;
const TYPEWRITER_COMMON_PREFIX_MIN_CHARS = 8;
const TYPEWRITER_COMMON_PREFIX_RATIO = 0.35;

export function ReportProgressSidebar({
  jobId,
  sections,
  isGenerating,
  done,
  caseId,
}: ReportProgressSidebarProps) {
  const router = useRouter();
  const [displayedEntries, setDisplayedEntries] = useState<TocEntry[]>([]);
  const previousJobIdRef = useRef<string | null>(null);
  const previousTargetEntriesRef = useRef<TocEntry[]>([]);
  const changedAtByIdRef = useRef<Map<string, number>>(new Map());
  const changeSequenceRef = useRef(0);
  const typingTimerRef = useRef<number | null>(null);
  const typingProgressRef = useRef<TypingProgress | null>(null);
  const terminal = !isGenerating;

  const targetEntries = useMemo<TocEntry[]>(() => buildTocEntries(sections), [sections]);

  useEffect(() => {
    return () => {
      if (typingTimerRef.current !== null) {
        window.clearTimeout(typingTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const isNewJob = previousJobIdRef.current !== jobId;
    if (isNewJob) {
      previousJobIdRef.current = jobId;
      previousTargetEntriesRef.current = [];
      changedAtByIdRef.current = new Map();
      changeSequenceRef.current = 0;
      typingProgressRef.current = null;
    }

    const previousTargetEntriesById = new Map(
      previousTargetEntriesRef.current.map((entry) => [entry.id, entry]),
    );
    const nextChangedAtById = isNewJob
      ? new Map<string, number>()
      : new Map(changedAtByIdRef.current);

    for (const entry of targetEntries) {
      const previousEntry = previousTargetEntriesById.get(entry.id);
      if (
        !previousEntry ||
        previousEntry.title !== entry.title ||
        previousEntry.subtitle !== entry.subtitle ||
        previousEntry.description !== entry.description ||
        previousEntry.status !== entry.status
      ) {
        changeSequenceRef.current += 1;
        nextChangedAtById.set(entry.id, changeSequenceRef.current);
      }
    }

    for (const entryId of Array.from(nextChangedAtById.keys())) {
      if (!targetEntries.some((entry) => entry.id === entryId)) {
        nextChangedAtById.delete(entryId);
      }
    }

    changedAtByIdRef.current = nextChangedAtById;
    previousTargetEntriesRef.current = targetEntries;

    setDisplayedEntries((currentEntries) =>
      synchronizeDisplayedEntries(currentEntries, targetEntries, {
        resetDescriptions: isNewJob,
        terminal,
      }),
    );
  }, [jobId, targetEntries, terminal]);

  useEffect(() => {
    if (typingTimerRef.current !== null) {
      window.clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }

    if (terminal) {
      typingProgressRef.current = null;
      return;
    }

    const activeEntryId = chooseTypingEntryId(
      targetEntries,
      displayedEntries,
      changedAtByIdRef.current,
    );
    if (!activeEntryId) {
      typingProgressRef.current = null;
      return;
    }

    const activeTargetEntry = targetEntries.find((entry) => entry.id === activeEntryId);
    const activeDisplayedEntry = displayedEntries.find((entry) => entry.id === activeEntryId);
    if (!activeTargetEntry || !activeDisplayedEntry) {
      typingProgressRef.current = null;
      return;
    }

    if (activeDisplayedEntry.description === activeTargetEntry.description) {
      return;
    }

    const now = performance.now();
    const currentProgress = typingProgressRef.current;
    if (
      !currentProgress ||
      currentProgress.id !== activeEntryId ||
      currentProgress.targetDescription !== activeTargetEntry.description
    ) {
      typingProgressRef.current = {
        id: activeEntryId,
        targetDescription: activeTargetEntry.description,
        lastTickAt: now,
        snapshotStartedAt: now,
        carry: 0,
      };
    }

    typingTimerRef.current = window.setTimeout(() => {
      const progress = typingProgressRef.current;
      if (!progress || progress.id !== activeEntryId) {
        return;
      }

      const tickAt = performance.now();
      const deltaMs = Math.max(tickAt - progress.lastTickAt, TYPEWRITER_TICK_MS);
      const elapsedSinceSnapshot = tickAt - progress.snapshotStartedAt;
      const charactersPerSecond =
        elapsedSinceSnapshot < TYPEWRITER_BURST_DURATION_MS
          ? TYPEWRITER_BURST_CHARS_PER_SECOND
          : TYPEWRITER_STEADY_CHARS_PER_SECOND;
      const totalBudget = progress.carry + (deltaMs * charactersPerSecond) / 1000;
      const nextCharacters = Math.max(1, Math.floor(totalBudget));

      progress.lastTickAt = tickAt;
      progress.carry = totalBudget - nextCharacters;

      setDisplayedEntries((currentEntries) =>
        currentEntries.map((entry) => {
          if (entry.id !== activeEntryId) {
            return entry;
          }

          const nextDescription = activeTargetEntry.description.slice(
            0,
            Math.min(
              entry.description.length + nextCharacters,
              activeTargetEntry.description.length,
            ),
          );
          if (nextDescription === entry.description) {
            return entry;
          }

          return {
            ...entry,
            description: nextDescription,
          };
        }),
      );
    }, TYPEWRITER_TICK_MS);

    return () => {
      if (typingTimerRef.current !== null) {
        window.clearTimeout(typingTimerRef.current);
        typingTimerRef.current = null;
      }
    };
  }, [displayedEntries, targetEntries, terminal]);

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
            ? 'Generating your litigation report...'
            : 'All sections have been generated.'}
        </p>
      </div>

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

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 0 8px' }}>
        {displayedEntries.length === 0 && isGenerating && (
          <div
            style={{
              padding: '12px 16px',
              fontSize: '12px',
              color: 'var(--text-tertiary)',
            }}
          >
            Starting...
          </div>
        )}
        {displayedEntries.map((entry) => (
          <div
            key={entry.id}
            style={{
              padding: '8px 16px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
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
                    color:
                      entry.status === 'pending'
                        ? 'var(--text-tertiary)'
                        : 'var(--text-primary)',
                    lineHeight: 1.3,
                    marginBottom: entry.subtitle || entry.description ? '3px' : 0,
                  }}
                >
                  {entry.title}
                </div>
                {entry.subtitle && (
                  <div
                    style={{
                      fontSize: '11px',
                      fontWeight: 500,
                      color:
                        entry.status === 'streaming'
                          ? 'var(--accent)'
                          : 'var(--text-secondary)',
                      lineHeight: 1.3,
                      marginBottom: entry.description ? '2px' : 0,
                    }}
                  >
                    {entry.subtitle}
                    {entry.status === 'streaming' ? '...' : ''}
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

function buildTocEntries(sections: SectionState[]): TocEntry[] {
  const entries: TocEntry[] = [];
  let current: TocEntry | null = null;

  for (const sectionState of sections) {
    if (
      sectionState.section.block_type === 'heading' &&
      sectionState.section.heading_level === 2
    ) {
      if (current) {
        entries.push(current);
      }
      current = {
        id: sectionState.section.canonical_block_id ?? sectionState.section.id,
        title: sectionState.section.text ?? '',
        subtitle: '',
        description: '',
        status: sectionState.streaming
          ? 'streaming'
          : sectionState.complete
            ? 'done'
            : 'pending',
      };
      continue;
    }

    if (!current) {
      continue;
    }

    if (sectionState.streaming) {
      current.status = 'streaming';
    } else if (sectionState.complete && current.status !== 'streaming') {
      current.status = 'done';
    }

    const blockType = sectionState.section.block_type;
    if (!current.subtitle) {
      if (blockType === 'image' || blockType === 'evidence_image') {
        current.subtitle = 'Generating image';
      } else if (blockType === 'video') {
        current.subtitle = 'Generating video';
      } else if (blockType === 'timeline') {
        current.subtitle = 'Building timeline';
      } else if (blockType === 'counter_argument') {
        current.subtitle = 'Analyzing counter-arguments';
      } else if (blockType === 'text') {
        current.subtitle = 'Writing analysis';
      }
    }

    if (blockType === 'text' && !current.description) {
      const raw = sectionState.text || sectionState.section.text || '';
      const clean = raw.replace(/\[\d+\]/g, '').trim();
      current.description = clean.slice(0, 90) + (clean.length > 90 ? '...' : '');
    }
  }

  if (current) {
    entries.push(current);
  }

  return entries;
}

function synchronizeDisplayedEntries(
  currentEntries: TocEntry[],
  targetEntries: TocEntry[],
  options: {
    resetDescriptions: boolean;
    terminal: boolean;
  },
): TocEntry[] {
  const currentEntriesById = new Map(currentEntries.map((entry) => [entry.id, entry]));

  return targetEntries.map((targetEntry) => {
    const currentEntry = currentEntriesById.get(targetEntry.id);

    return {
      ...targetEntry,
      description: resolveDisplayedDescription(
        currentEntry?.description ?? '',
        targetEntry.description,
        options,
      ),
    };
  });
}

function resolveDisplayedDescription(
  currentDescription: string,
  targetDescription: string,
  options: {
    resetDescriptions: boolean;
    terminal: boolean;
  },
): string {
  if (options.terminal) {
    return targetDescription;
  }

  if (options.resetDescriptions || !currentDescription || !targetDescription) {
    return '';
  }

  if (
    currentDescription === targetDescription ||
    targetDescription.startsWith(currentDescription)
  ) {
    return currentDescription;
  }

  const sharedPrefixLength = getSharedPrefixLength(currentDescription, targetDescription);
  const minimumMeaningfulPrefix = Math.max(
    TYPEWRITER_COMMON_PREFIX_MIN_CHARS,
    Math.floor(
      Math.min(currentDescription.length, targetDescription.length) *
        TYPEWRITER_COMMON_PREFIX_RATIO,
    ),
  );

  if (sharedPrefixLength >= minimumMeaningfulPrefix) {
    return targetDescription.slice(0, sharedPrefixLength);
  }

  return targetDescription;
}

function chooseTypingEntryId(
  targetEntries: TocEntry[],
  displayedEntries: TocEntry[],
  changedAtById: Map<string, number>,
): string | null {
  const displayedEntriesById = new Map(displayedEntries.map((entry) => [entry.id, entry]));
  const needsReveal = (entry: TocEntry) =>
    (displayedEntriesById.get(entry.id)?.description ?? '') !== entry.description;

  const streamingEntry = targetEntries.find(
    (entry) => entry.status === 'streaming' && needsReveal(entry),
  );
  if (streamingEntry) {
    return streamingEntry.id;
  }

  const changedIncompleteEntries = targetEntries
    .filter((entry) => entry.status !== 'done' && needsReveal(entry))
    .sort(
      (left, right) =>
        (changedAtById.get(right.id) ?? 0) - (changedAtById.get(left.id) ?? 0),
    );
  if (changedIncompleteEntries.length > 0) {
    return changedIncompleteEntries[0].id;
  }

  return targetEntries.find(needsReveal)?.id ?? null;
}

function getSharedPrefixLength(left: string, right: string): number {
  const limit = Math.min(left.length, right.length);
  let index = 0;

  while (index < limit && left[index] === right[index]) {
    index += 1;
  }

  return index;
}
