'use client';

import React, { useRef } from 'react';
import { Paperclip, Zap } from 'lucide-react';

interface CanvasToolbarProps {
  evidenceCount: number;
  isAnalyzing: boolean;
  isGenerating: boolean;
  caseId: string | null;
  onAddFiles: (files: File[]) => void;
  onGenerateReport: () => void;
}

export function CanvasToolbar({
  evidenceCount,
  isAnalyzing,
  isGenerating,
  caseId,
  onAddFiles,
  onGenerateReport,
}: CanvasToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const busy = isAnalyzing || isGenerating;
  const canGenerate = evidenceCount > 0 && !busy;

  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'stretch',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        overflow: 'hidden',
        fontFamily: 'DM Sans, sans-serif',
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0) onAddFiles(files);
          e.target.value = '';
        }}
      />

      <ToolbarButton
        icon={<Paperclip size={13} strokeWidth={2} />}
        label="Add Files"
        onClick={() => fileInputRef.current?.click()}
        disabled={false}
      />

      <div style={{ width: '1px', background: 'var(--border)', flexShrink: 0 }} />

      <ToolbarButton
        icon={<Zap size={13} strokeWidth={2} />}
        label={busy ? (isAnalyzing ? 'Analyzing…' : 'Generating…') : 'Generate Report'}
        onClick={onGenerateReport}
        disabled={!canGenerate}
        accent={canGenerate}
        pulsing={canGenerate}
      />
    </div>
  );
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  accent?: boolean;
  pulsing?: boolean;
}

function ToolbarButton({
  icon,
  label,
  onClick,
  disabled,
  accent,
  pulsing,
}: ToolbarButtonProps) {
  const [hovered, setHovered] = React.useState(false);

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '8px 14px',
        background: hovered && !disabled ? 'var(--bg-elevated)' : 'transparent',
        border: 'none',
        cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'DM Sans, sans-serif',
        fontSize: '13px',
        fontWeight: 500,
        color: disabled
          ? 'var(--text-tertiary)'
          : accent
            ? 'var(--accent)'
            : 'var(--text-primary)',
        transition: 'background 0.15s, color 0.15s',
        outline: 'none',
        animation: pulsing ? 'analyzeButtonPulse 2s ease-in-out infinite' : undefined,
      }}
    >
      <style>{`
        @keyframes analyzeButtonPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
      {icon}
      {label}
    </button>
  );
}
