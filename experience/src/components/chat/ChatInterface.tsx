'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage as ChatMessageType } from '@/lib/types';
import { ChatMessage } from './ChatMessage';

interface ChatInterfaceProps {
  messages: ChatMessageType[];
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInterface({ messages, onSend, disabled, placeholder }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'flex-start',
              paddingBottom: '40px',
            }}
          >
            <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', lineHeight: 1.7 }}>
              Start by describing your case — the incident, the parties involved, the legal theory you're pursuing.
              Or just start uploading evidence and the system will analyze it.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          borderTop: '1px solid var(--border)',
          padding: '12px 24px',
        }}
      >
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder || 'Describe your case, or just start uploading evidence...'}
            style={{
              width: '100%',
              border: 'none',
              borderBottom: '1px solid var(--border)',
              background: 'transparent',
              padding: '8px 0',
              fontSize: '14px',
              color: 'var(--text-primary)',
              outline: 'none',
              fontFamily: 'DM Sans, sans-serif',
              transition: 'border-color 200ms',
            }}
            onFocus={(e) => { e.currentTarget.style.borderBottomColor = 'var(--accent)'; }}
            onBlur={(e) => { e.currentTarget.style.borderBottomColor = 'var(--border)'; }}
          />
        </form>
      </div>
    </div>
  );
}
