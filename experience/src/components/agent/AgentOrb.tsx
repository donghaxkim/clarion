'use client';

import { useState, useRef, useCallback } from 'react';
import type { AgentState } from '@livekit/components-react';
import { useTheme } from 'next-themes';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';
import type { VoiceOrbState } from '@/lib/voice';

const CYCLE: VoiceOrbState[] = ['idle', 'listening', 'speaking'];

const MAGNETIC_SPRING = { stiffness: 150, damping: 15, mass: 0.1 };
const SCALE_SPRING = { stiffness: 400, damping: 30 };
const GLOW_SPRING = { stiffness: 200, damping: 25 };

interface AgentOrbProps {
  state?: VoiceOrbState;
  onClick?: () => void;
  disabled?: boolean;
  caption?: string;
}

export function AgentOrb({ state, onClick, disabled = false, caption }: AgentOrbProps) {
  const [stateIndex, setStateIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const { resolvedTheme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);

  const orbState = state ?? CYCLE[stateIndex];
  const themeMode = resolvedTheme === 'light' ? 'light' : 'dark';
  const visualState = mapOrbStateToVisualizerState(orbState);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const offsetX = useSpring(mouseX, MAGNETIC_SPRING);
  const offsetY = useSpring(mouseY, MAGNETIC_SPRING);

  const scaleRaw = useMotionValue(1);
  const scale = useSpring(scaleRaw, SCALE_SPRING);

  const glowRaw = useMotionValue(0);
  const glow = useSpring(glowRaw, GLOW_SPRING);
  const dropShadowBlur = useTransform(glow, [0, 1], [24, 44]);
  const dropShadowAlpha = useTransform(glow, [0, 1], [0.6, 0.9]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!containerRef.current || disabled) return;
      const rect = containerRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) * 0.15;
      const dy = (e.clientY - cy) * 0.15;
      const maxPull = 6;
      mouseX.set(Math.max(-maxPull, Math.min(maxPull, dx)));
      mouseY.set(Math.max(-maxPull, Math.min(maxPull, dy)));
    },
    [disabled, mouseX, mouseY]
  );

  const handleMouseEnter = useCallback(() => {
    if (disabled) {
      return;
    }
    setIsHovered(true);
    scaleRaw.set(1.06);
    glowRaw.set(1);
  }, [disabled, scaleRaw, glowRaw]);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    scaleRaw.set(1);
    glowRaw.set(0);
    mouseX.set(0);
    mouseY.set(0);
  }, [scaleRaw, glowRaw, mouseX, mouseY]);

  const handleMouseDown = useCallback(() => {
    if (disabled) {
      return;
    }
    scaleRaw.set(0.92);
  }, [disabled, scaleRaw]);

  const handleMouseUp = useCallback(() => {
    scaleRaw.set(isHovered && !disabled ? 1.06 : 1);
  }, [scaleRaw, isHovered, disabled]);

  function handleClick() {
    if (disabled) {
      return;
    }
    if (onClick) {
      onClick();
      return;
    }
    if (!state) {
      setStateIndex((i) => (i + 1) % CYCLE.length);
    }
  }

  return (
    <motion.div
      ref={containerRef}
      role="button"
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (!disabled && e.key === 'Enter') {
          handleClick();
        }
      }}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      style={{
        cursor: disabled ? 'not-allowed' : 'pointer',
        x: offsetX,
        y: offsetY,
        scale,
        opacity: disabled ? 0.65 : 1,
        filter: useTransform(
          [dropShadowBlur, dropShadowAlpha],
          ([blur, alpha]) =>
            `drop-shadow(0 0 ${blur}px rgba(139, 105, 20, ${alpha}))`
        ),
        willChange: 'transform, filter',
      }}
    >
      <AgentAudioVisualizerAura
        size="xl"
        color="#8B6914"
        colorShift={0}
        state={visualState}
        themeMode={themeMode}
        className="aspect-square size-auto w-full"
      />
      <motion.p
        className="text-center text-sm mt-2"
        style={{
          color: '#9ca3af',
          fontFamily: "'DM Sans', sans-serif",
          userSelect: 'none',
        }}
        animate={{
          opacity: isHovered || disabled ? 1 : 0.6,
          y: isHovered && !disabled ? -2 : 0,
        }}
        transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
      >
        {caption ?? formatOrbStateLabel(orbState)}
      </motion.p>
    </motion.div>
  );
}

function mapOrbStateToVisualizerState(state: VoiceOrbState): AgentState {
  switch (state) {
    case 'disconnected':
      return 'disconnected';
    case 'connecting':
      return 'connecting';
    case 'idle':
      return 'idle';
    case 'listening':
      return 'listening';
    case 'thinking':
      return 'thinking';
    case 'speaking':
      return 'speaking';
    case 'error':
      return 'failed';
    case 'awaiting_confirm':
      return 'thinking';
    default:
      return 'idle';
  }
}

function formatOrbStateLabel(state: VoiceOrbState): string {
  switch (state) {
    case 'awaiting_confirm':
      return 'awaiting confirm';
    default:
      return state;
  }
}
