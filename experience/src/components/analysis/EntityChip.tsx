'use client';

import React from 'react';
import { Entity } from '@/lib/types';
import { EntityTypeDot } from '@/components/ui/Badge';

interface EntityChipProps {
  entity: Entity;
  onClick?: (entity: Entity) => void;
}

export function EntityChip({ entity, onClick }: EntityChipProps) {
  return (
    <div
      onClick={() => onClick?.(entity)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '5px 10px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'border-color 200ms',
        fontSize: '12px',
        color: 'var(--text-primary)',
        fontWeight: 500,
      }}
      onMouseEnter={(e) => onClick && (e.currentTarget.style.borderColor = 'var(--border-focus)')}
      onMouseLeave={(e) => onClick && (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <EntityTypeDot type={entity.type} />
      <span>{entity.name}</span>
    </div>
  );
}
