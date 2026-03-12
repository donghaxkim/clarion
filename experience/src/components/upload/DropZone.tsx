'use client';

import React, { useState, useRef } from 'react';
import { Upload } from 'lucide-react';

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  uploading?: boolean;
}

export function DropZone({ onFiles, uploading }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) onFiles(files);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) onFiles(files);
    e.target.value = '';
  }

  return (
    <div
      onClick={() => !uploading && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      style={{
        height: '120px',
        border: `1px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: '6px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        cursor: uploading ? 'wait' : 'pointer',
        transition: 'border-color 200ms',
        background: dragOver ? 'var(--accent-light)' : 'transparent',
        marginBottom: '16px',
      }}
    >
      <Upload
        size={18}
        strokeWidth={1.5}
        style={{ color: dragOver ? 'var(--accent)' : 'var(--text-tertiary)' }}
      />
      <span
        style={{
          fontSize: '12px',
          color: dragOver ? 'var(--accent)' : 'var(--text-tertiary)',
          textAlign: 'center',
          lineHeight: 1.4,
          transition: 'color 200ms',
        }}
      >
        Drop files here — PDF, images, audio, video
        <br />
        <span style={{ fontSize: '11px', opacity: 0.7 }}>or click to browse</span>
      </span>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,.mp4,.mov,.m4a,.mp3,.wav"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
    </div>
  );
}
