'use client';

import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  disabled,
  ...props
}: ButtonProps) {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    fontFamily: 'DM Sans, sans-serif',
    fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'border-color 200ms, background 200ms, color 200ms',
    whiteSpace: 'nowrap',
    borderRadius: '6px',
    border: '1px solid transparent',
    outline: 'none',
  };

  const sizeStyle: React.CSSProperties =
    size === 'sm'
      ? { fontSize: '12px', padding: '5px 10px' }
      : size === 'lg'
      ? { fontSize: '14px', padding: '10px 20px' }
      : { fontSize: '13px', padding: '7px 14px' };

  let variantStyle: React.CSSProperties = {};
  if (variant === 'primary') {
    variantStyle = disabled
      ? {
          background: 'var(--bg-elevated)',
          color: 'var(--text-tertiary)',
          borderColor: 'var(--border)',
        }
      : {
          background: 'var(--accent)',
          color: '#FFFFFF',
          borderColor: 'var(--accent)',
        };
  } else if (variant === 'secondary') {
    variantStyle = {
      background: 'var(--bg-surface)',
      color: disabled ? 'var(--text-tertiary)' : 'var(--text-primary)',
      borderColor: 'var(--border)',
    };
  } else if (variant === 'ghost') {
    variantStyle = {
      background: 'transparent',
      color: disabled ? 'var(--text-tertiary)' : 'var(--text-secondary)',
      borderColor: 'transparent',
    };
  }

  return (
    <button
      disabled={disabled}
      style={{ ...baseStyle, ...sizeStyle, ...variantStyle }}
      className={className}
      {...props}
    >
      {children}
    </button>
  );
}
