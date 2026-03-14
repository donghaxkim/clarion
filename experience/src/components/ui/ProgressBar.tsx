'use client';

import React from 'react';

interface ProgressBarProps {
  progress?: number; // 0-100, undefined = indeterminate
  className?: string;
  color?: string;
}

export function ProgressBar({ progress, className = '', color = 'var(--accent)' }: ProgressBarProps) {
  const isIndeterminate = progress === undefined;

  return (
    <div
      className={className}
      style={{
        height: '2px',
        background: 'var(--border)',
        borderRadius: '1px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {isIndeterminate ? (
        <div
          className="progress-indeterminate"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            height: '100%',
            width: '25%',
            background: color,
            borderRadius: '1px',
          }}
        />
      ) : (
        <div
          style={{
            height: '100%',
            width: `${Math.min(100, Math.max(0, progress))}%`,
            background: color,
            borderRadius: '1px',
            transition: 'width 300ms ease',
          }}
        />
      )}
    </div>
  );
}
