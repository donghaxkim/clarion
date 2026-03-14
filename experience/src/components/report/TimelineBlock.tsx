'use client';

import React from 'react';
import { TimelineEvent } from '@/lib/types';

interface TimelineBlockProps {
  events: TimelineEvent[];
}

export function TimelineBlock({ events }: TimelineBlockProps) {
  return (
    <div style={{ overflowX: 'auto', paddingBottom: '8px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          minWidth: `${events.length * 140}px`,
          position: 'relative',
          padding: '32px 0',
        }}
      >
        {/* Horizontal line */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '0',
            right: '0',
            height: '1px',
            background: 'var(--border)',
            transform: 'translateY(-50%)',
          }}
        />

        {events.map((event, i) => {
          const isAbove = i % 2 === 0;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                position: 'relative',
              }}
            >
              {/* Label above */}
              {isAbove && (
                <div style={{ marginBottom: '8px', textAlign: 'center', maxWidth: '120px' }}>
                  <span
                    style={{
                      display: 'block',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      marginBottom: '2px',
                    }}
                  >
                    {event.label}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      fontSize: '10px',
                      fontFamily: 'DM Mono, monospace',
                      color: 'var(--accent)',
                    }}
                  >
                    {event.time}
                  </span>
                </div>
              )}

              {/* Dot */}
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  border: '2px solid var(--bg)',
                  zIndex: 1,
                  flexShrink: 0,
                }}
              />

              {/* Label below */}
              {!isAbove && (
                <div style={{ marginTop: '8px', textAlign: 'center', maxWidth: '120px' }}>
                  <span
                    style={{
                      display: 'block',
                      fontSize: '10px',
                      fontFamily: 'DM Mono, monospace',
                      color: 'var(--accent)',
                      marginBottom: '2px',
                    }}
                  >
                    {event.time}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                    }}
                  >
                    {event.label}
                  </span>
                </div>
              )}

              {/* Detail tooltip on hover — simplified as title attr */}
              {event.detail && (
                <span
                  title={event.detail}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    cursor: 'default',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
