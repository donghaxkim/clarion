'use client';

import React, { memo, useEffect, useRef } from 'react';
import { NodeProps, Handle, Position, Node } from '@xyflow/react';
import { EvidenceType } from '@/lib/types';
import {
  getEvidenceColor,
  getEvidenceLabel,
  getEvidenceThumbnailBg,
  getAudioWaveformBars,
  getEntityTypeColor,
  isImageFile,
  isAudioFile,
  isPdfFile,
  isVideoFile,
} from '../utils/thumbnail';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface EvidenceNodeData {
  evidenceId: string;
  filename: string;
  evidenceType: EvidenceType;
  summary: string;
  entities: { type: string; name: string }[];
  entityCount: number;
  factCount: number;
  labels: string[];
  nodeStatus: 'uploading' | 'parsing' | 'complete';
  uploadProgress?: number;
  isIndexed?: boolean;
  pinned?: boolean;
  analyzing?: boolean;
  hasConnections?: boolean;
  lastValidPosition?: { x: number; y: number };
  [key: string]: unknown;
}

export type EvidenceNodeType = Node<EvidenceNodeData, 'evidenceNode'>;

// ─── Sub-components ────────────────────────────────────────────────────────────

function Thumbnail({ filename, evidenceType, status }: {
  filename: string;
  evidenceType: EvidenceType;
  status: EvidenceNodeData['nodeStatus'];
}) {
  const bgColor = getEvidenceThumbnailBg(evidenceType);
  const accentColor = getEvidenceColor(evidenceType);

  const containerStyle: React.CSSProperties = {
    width: '100%',
    height: '140px',
    borderRadius: '4px',
    overflow: 'hidden',
    background: bgColor,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    marginBottom: '12px',
    flexShrink: 0,
  };

  if (status === 'uploading') {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', opacity: 0.5 }}>
          <UploadIcon color={accentColor} />
        </div>
      </div>
    );
  }

  if (status === 'parsing') {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center' }}>
          <div className="shimmer" style={{ width: '100%', height: '100%', position: 'absolute', inset: 0, opacity: 0.5 }} />
          <ParsingSpinner color={accentColor} />
        </div>
      </div>
    );
  }

  // Complete state
  if (isImageFile(filename)) {
    return (
      <div style={containerStyle}>
        {/* Real image thumbnail would be loaded from API */}
        <ImagePlaceholder color={accentColor} />
      </div>
    );
  }

  if (isAudioFile(filename)) {
    return (
      <div style={containerStyle}>
        <AudioWaveform filename={filename} color={accentColor} />
      </div>
    );
  }

  if (isVideoFile(filename)) {
    return (
      <div style={containerStyle}>
        <VideoPlaceholder color={accentColor} />
      </div>
    );
  }

  // PDF / default
  return (
    <div style={containerStyle}>
      <PdfPlaceholder color={accentColor} />
    </div>
  );
}

function PdfPlaceholder({ color }: { color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', opacity: 0.6 }}>
      <svg width="32" height="40" viewBox="0 0 32 40" fill="none">
        <rect x="1" y="1" width="30" height="38" rx="3" stroke={color} strokeWidth="1.5" fill="none" />
        <path d="M8 1V11H1" stroke={color} strokeWidth="1.5" fill="none" />
        <line x1="8" y1="18" x2="24" y2="18" stroke={color} strokeWidth="1" strokeLinecap="round" />
        <line x1="8" y1="22" x2="24" y2="22" stroke={color} strokeWidth="1" strokeLinecap="round" />
        <line x1="8" y1="26" x2="20" y2="26" stroke={color} strokeWidth="1" strokeLinecap="round" />
        <line x1="8" y1="30" x2="22" y2="30" stroke={color} strokeWidth="1" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function ImagePlaceholder({ color }: { color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', opacity: 0.6 }}>
      <svg width="40" height="32" viewBox="0 0 40 32" fill="none">
        <rect x="1" y="1" width="38" height="30" rx="3" stroke={color} strokeWidth="1.5" fill="none" />
        <circle cx="13" cy="11" r="3" stroke={color} strokeWidth="1.5" fill="none" />
        <path d="M1 21L12 13L19 19L26 14L39 21" stroke={color} strokeWidth="1.5" fill="none" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function VideoPlaceholder({ color }: { color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', opacity: 0.6 }}>
      <svg width="40" height="32" viewBox="0 0 40 32" fill="none">
        <rect x="1" y="1" width="28" height="30" rx="3" stroke={color} strokeWidth="1.5" fill="none" />
        <path d="M29 10L39 6V26L29 22V10Z" stroke={color} strokeWidth="1.5" fill="none" strokeLinejoin="round" />
        <path d="M11 11L11 21L19 16L11 11Z" fill={color} opacity="0.5" />
      </svg>
    </div>
  );
}

function AudioWaveform({ filename, color }: { filename: string; color: string }) {
  const bars = getAudioWaveformBars(filename, 28);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '0 12px', height: '100%' }}>
      {bars.map((height, i) => (
        <div
          key={i}
          style={{
            width: '3px',
            height: `${height * 80}%`,
            background: color,
            borderRadius: '2px',
            opacity: 0.6,
            flexShrink: 0,
          }}
        />
      ))}
    </div>
  );
}

function UploadIcon({ color }: { color: string }) {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path d="M14 20V10M14 10L9 15M14 10L19 15" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 22H23" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}

function ParsingSpinner({ color }: { color: string }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="1.5" strokeDasharray="40 20" strokeLinecap="round" />
    </svg>
  );
}

// ─── Status dot ────────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: EvidenceNodeData['nodeStatus'] }) {
  const colors: Record<string, string> = {
    uploading: '#C98A2E',
    parsing: '#C9A84C',
    complete: '#6B9B7E',
  };
  const labels: Record<string, string> = {
    uploading: 'uploading',
    parsing: 'parsing',
    complete: '',
  };

  if (status === 'complete') return null;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <div
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: colors[status],
          animation: 'nodePulse 1.5s ease-in-out infinite',
        }}
      />
      <span style={{ fontSize: '10px', color: colors[status], fontWeight: 500 }}>
        {labels[status]}
      </span>
    </div>
  );
}

// ─── Main Node ─────────────────────────────────────────────────────────────────

function EvidenceNodeComponent({ data, selected }: NodeProps<EvidenceNodeType>) {
  const {
    evidenceType,
    filename,
    summary,
    entities,
    entityCount,
    factCount,
    nodeStatus,
    uploadProgress,
    analyzing,
    hasConnections,
  } = data;

  const accentColor = getEvidenceColor(evidenceType);
  const typeLabel = getEvidenceLabel(evidenceType);
  const nodeRef = useRef<HTMLDivElement>(null);

  // Trigger completion pop animation
  useEffect(() => {
    if (nodeStatus === 'complete' && nodeRef.current) {
      nodeRef.current.classList.add('evidence-node--complete-pop');
      const timer = setTimeout(() => {
        nodeRef.current?.classList.remove('evidence-node--complete-pop');
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [nodeStatus]);

  const visibleEntities = entities.slice(0, 3);
  const extraEntities = entities.length > 3 ? entities.length - 3 : 0;

  const containerClass = [
    nodeStatus === 'uploading' ? 'evidence-node--uploading' : '',
    analyzing ? 'evidence-node--analyzing' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      {/* React Flow handles — show when has connections */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          width: '8px', height: '8px',
          background: 'var(--border)',
          border: '1px solid var(--bg-surface)',
          opacity: hasConnections ? 1 : 0,
          transition: 'opacity 0.15s',
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          width: '8px', height: '8px',
          background: 'var(--border)',
          border: '1px solid var(--bg-surface)',
          opacity: hasConnections ? 1 : 0,
          transition: 'opacity 0.15s',
        }}
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left"
        style={{
          width: '8px', height: '8px',
          background: 'var(--border)',
          border: '1px solid var(--bg-surface)',
          opacity: hasConnections ? 1 : 0,
          transition: 'opacity 0.15s',
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{
          width: '8px', height: '8px',
          background: 'var(--border)',
          border: '1px solid var(--bg-surface)',
          opacity: hasConnections ? 1 : 0,
          transition: 'opacity 0.15s',
        }}
      />

      {/* Card */}
      <div
        ref={nodeRef}
        className={containerClass}
        style={{
          width: '260px',
          background: 'var(--bg-surface)',
          borderTop: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
          borderRight: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
          borderBottom: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
          borderLeft: `3px solid ${accentColor}`,
          borderRadius: '6px',
          boxShadow: selected
            ? '0 2px 8px rgba(0,0,0,0.08)'
            : '0 1px 3px rgba(0,0,0,0.04)',
          padding: '14px 14px 12px',
          cursor: 'grab',
          userSelect: 'none',
          position: 'relative',
          fontFamily: 'DM Sans, sans-serif',
        }}
      >
        {/* Upload progress bar */}
        {nodeStatus === 'uploading' && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '2px',
              background: 'var(--accent-light)',
              borderRadius: '6px 6px 0 0',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${uploadProgress ?? 50}%`,
                background: 'var(--accent)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        )}

        {/* Header: type label + status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '10px',
          }}
        >
          <span
            style={{
              fontSize: '10px',
              fontWeight: 600,
              letterSpacing: '0.06em',
              color: accentColor,
              textTransform: 'uppercase',
            }}
          >
            {typeLabel}
          </span>
          <StatusDot status={nodeStatus} />
        </div>

        {/* Thumbnail */}
        <Thumbnail
          filename={filename}
          evidenceType={evidenceType}
          status={nodeStatus}
        />

        {/* Filename */}
        <div
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--text-primary)',
            marginBottom: '6px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={filename}
        >
          {filename}
        </div>

        {/* Summary */}
        {nodeStatus === 'complete' ? (
          <div
            style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              marginBottom: '10px',
            }}
          >
            {summary}
          </div>
        ) : (
          <div
            style={{
              fontSize: '12px',
              color: 'var(--text-tertiary)',
              marginBottom: '10px',
              fontStyle: 'italic',
            }}
          >
            {nodeStatus === 'parsing' ? 'Analyzing document...' : 'Uploading...'}
          </div>
        )}

        {/* Entity pills */}
        {nodeStatus === 'complete' && entities.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '4px',
              marginBottom: '8px',
            }}
          >
            {visibleEntities.map((entity, i) => (
              <div
                key={i}
                style={{
                  fontSize: '11px',
                  background: 'var(--bg-elevated)',
                  borderRadius: '4px',
                  padding: '2px 6px',
                  color: 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  border: '1px solid var(--border)',
                }}
              >
                <span
                  style={{
                    width: '5px',
                    height: '5px',
                    borderRadius: '50%',
                    background: getEntityTypeColor(entity.type),
                    flexShrink: 0,
                    display: 'inline-block',
                  }}
                />
                {entity.name}
              </div>
            ))}
            {extraEntities > 0 && (
              <div
                style={{
                  fontSize: '11px',
                  background: 'var(--bg-elevated)',
                  borderRadius: '4px',
                  padding: '2px 6px',
                  color: 'var(--text-tertiary)',
                  border: '1px solid var(--border)',
                }}
              >
                +{extraEntities} more
              </div>
            )}
          </div>
        )}

        {/* Metadata line */}
        {nodeStatus === 'complete' && (
          <div
            style={{
              fontSize: '11px',
              color: 'var(--text-tertiary)',
              fontFamily: 'DM Mono, monospace',
              borderTop: '1px solid var(--border)',
              paddingTop: '8px',
              marginTop: '4px',
            }}
          >
            {entityCount > 0 && `${entityCount} ${entityCount === 1 ? 'entity' : 'entities'}`}
            {entityCount > 0 && factCount > 0 && ' · '}
            {factCount > 0 && `${factCount} facts`}
          </div>
        )}
      </div>
    </>
  );
}

export const EvidenceNode = memo(EvidenceNodeComponent);
