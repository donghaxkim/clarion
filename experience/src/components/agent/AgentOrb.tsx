'use client';

import { useState } from 'react';
import type { AgentState } from '@livekit/components-react';
import { useTheme } from 'next-themes';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';

const CYCLE: AgentState[] = ['idle', 'listening', 'speaking'];

export function AgentOrb() {
  const [stateIndex, setStateIndex] = useState(0);
  const { resolvedTheme } = useTheme();

  const mockState = CYCLE[stateIndex];
  // Ternary required: resolvedTheme is string | undefined; component expects 'light' | 'dark'
  const themeMode = resolvedTheme === 'light' ? 'light' : 'dark';

  function handleClick() {
    setStateIndex((i) => (i + 1) % CYCLE.length);
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      style={{ cursor: 'pointer' }}
    >
      <AgentAudioVisualizerAura
        state={mockState}
        color="#1FD5F9"
        colorShift={1.95}
        size="xl"
        themeMode={themeMode}
        className="aspect-square w-full"
      />
      {/* Dev label — remove when connecting real LiveKit */}
      <div
        style={{
          textAlign: 'center',
          fontSize: '10px',
          color: 'var(--text-tertiary)',
          marginTop: '4px',
          fontFamily: 'DM Mono, monospace',
          userSelect: 'none',
        }}
      >
        {mockState}
      </div>
    </div>
  );
}
