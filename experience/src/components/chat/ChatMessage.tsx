'use client';

import React from 'react';
import { ChatMessage as ChatMessageType } from '@/lib/types';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '12px' }}>
        <div
          style={{
            background: 'var(--bg-elevated)',
            borderRadius: '6px',
            padding: '10px 14px',
            maxWidth: '72%',
            fontSize: '14px',
            color: 'var(--text-primary)',
            lineHeight: 1.5,
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
      <div
        style={{
          maxWidth: '72%',
          fontSize: '14px',
          color: 'var(--text-primary)',
          lineHeight: 1.6,
          borderLeft: '3px solid var(--accent)',
          paddingLeft: '12px',
          paddingTop: '2px',
          paddingBottom: '2px',
        }}
      >
        {message.content}
      </div>
    </div>
  );
}
