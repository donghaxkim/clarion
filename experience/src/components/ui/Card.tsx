'use client';

import React, { useState } from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
  evidenceColor?: string;
  noPadding?: boolean;
}

export function Card({ children, className = '', style = {}, onClick, evidenceColor, noPadding }: CardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered && onClick ? 'var(--border-focus)' : 'var(--border)'}`,
        borderRadius: '6px',
        padding: noPadding ? 0 : '20px',
        cursor: onClick ? 'pointer' : undefined,
        transition: 'border-color 200ms',
        position: 'relative',
        ...(evidenceColor && {
          borderLeft: `3px solid ${evidenceColor}`,
          paddingLeft: '17px',
        }),
        ...style,
      }}
      className={className}
    >
      {children}
    </div>
  );
}
