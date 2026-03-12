'use client';

import { useState } from 'react';
import type { AgentState } from '@livekit/components-react';
import { useTheme } from 'next-themes';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';

const CYCLE: AgentState[] = ['idle', 'listening', 'speaking'];

interface AgentOrbProps {
  state?: AgentState;
}

export function AgentOrb({ state }: AgentOrbProps) {
  const [stateIndex, setStateIndex] = useState(0);
  const { resolvedTheme } = useTheme();

  const agentState = state ?? CYCLE[stateIndex];
  const themeMode = resolvedTheme === 'light' ? 'light' : 'dark';

  function handleClick() {
    if (!state) setStateIndex((i) => (i + 1) % CYCLE.length);
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      style={{
        cursor: 'pointer',
        filter: 'drop-shadow(0 0 24px rgba(139, 105, 20, 0.6))',
        transform: 'scale(1.15)',
      }}
    >
      <AgentAudioVisualizerAura
        size="xl"
        color="#8B6914"
        colorShift={0}
        state={agentState}
        themeMode={themeMode}
        className="aspect-square size-auto w-full"
      />
      <p className="text-center text-sm mt-2" style={{ color: '#9ca3af', fontFamily: "'DM Sans', sans-serif" }}>
        {agentState}...
      </p>
    </div>
  );
}
