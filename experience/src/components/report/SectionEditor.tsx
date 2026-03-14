'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Send } from 'lucide-react';
import { ReportSection } from '@/lib/types';
import { editSection } from '@/lib/api';

interface SectionEditorProps {
  section: ReportSection;
  caseId: string;
  onClose: () => void;
  onUpdated: (sectionId: string) => void;
}

export function SectionEditor({ section, caseId, onClose, onUpdated }: SectionEditorProps) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!instruction.trim() || loading) return;
    setLoading(true);
    try {
      await editSection(caseId, section.id, instruction.trim());
      setDone(true);
      onUpdated(section.id);
      setTimeout(onClose, 1200);
    } catch {
      setLoading(false);
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        key="editor-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 40, background: 'rgba(26,26,26,0.1)' }}
      />

      <motion.div
        key="editor-panel"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '360px',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Edit Section</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', display: 'flex' }}
          >
            <X size={15} strokeWidth={1.5} />
          </button>
        </div>

        {/* Current text */}
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            maxHeight: '200px',
            overflowY: 'auto',
          }}
        >
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {section.text || `[${section.block_type} block]`}
          </p>
        </div>

        {/* Input */}
        <div style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column' }}>
          {done ? (
            <p style={{ fontSize: '13px', color: 'var(--severity-low)', lineHeight: 1.5 }}>
              Section updated. Closing...
            </p>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                How should this change?
              </label>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                disabled={loading}
                placeholder="e.g. Make this more concise, or add emphasis on the speed discrepancy..."
                style={{
                  flex: 1,
                  resize: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontSize: '13px',
                  fontFamily: 'DM Sans, sans-serif',
                  color: 'var(--text-primary)',
                  background: 'var(--bg-surface)',
                  outline: 'none',
                  minHeight: '100px',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--border-focus)'; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
              />
              <button
                type="submit"
                disabled={!instruction.trim() || loading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  background: loading || !instruction.trim() ? 'var(--bg-elevated)' : 'var(--accent)',
                  color: loading || !instruction.trim() ? 'var(--text-tertiary)' : '#fff',
                  border: '1px solid transparent',
                  borderRadius: '6px',
                  cursor: loading || !instruction.trim() ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: 500,
                  fontFamily: 'DM Sans, sans-serif',
                  transition: 'background 200ms',
                }}
              >
                <Send size={13} strokeWidth={1.5} />
                {loading ? 'Updating...' : 'Apply'}
              </button>
            </form>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
