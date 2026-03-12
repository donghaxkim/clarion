'use client';

import { useState, useRef, useCallback } from 'react';
import type { AgentState } from '@livekit/components-react';
import { useTheme } from 'next-themes';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';

const CYCLE: AgentState[] = ['idle', 'listening', 'speaking'];

// Spring configs — Apple-style responsiveness
const MAGNETIC_SPRING = { stiffness: 150, damping: 15, mass: 0.1 };
const SCALE_SPRING = { stiffness: 400, damping: 30 };
const GLOW_SPRING = { stiffness: 200, damping: 25 };

interface AgentOrbProps {
  state?: AgentState;
}

export function AgentOrb({ state }: AgentOrbProps) {
  const [stateIndex, setStateIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const { resolvedTheme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);

  const agentState = state ?? CYCLE[stateIndex];
  const themeMode = resolvedTheme === 'light' ? 'light' : 'dark';

  // Magnetic offset — orb subtly follows the cursor
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const offsetX = useSpring(mouseX, MAGNETIC_SPRING);
  const offsetY = useSpring(mouseY, MAGNETIC_SPRING);

  // Scale
  const scaleRaw = useMotionValue(1);
  const scale = useSpring(scaleRaw, SCALE_SPRING);

  // Glow intensity
  const glowRaw = useMotionValue(0);
  const glow = useSpring(glowRaw, GLOW_SPRING);
  const dropShadowBlur = useTransform(glow, [0, 1], [24, 44]);
  const dropShadowAlpha = useTransform(glow, [0, 1], [0.6, 0.9]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      // Magnetic pull: offset toward cursor, clamped
      const dx = (e.clientX - cx) * 0.15;
      const dy = (e.clientY - cy) * 0.15;
      const maxPull = 6;
      mouseX.set(Math.max(-maxPull, Math.min(maxPull, dx)));
      mouseY.set(Math.max(-maxPull, Math.min(maxPull, dy)));
    },
    [mouseX, mouseY]
  );

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
    scaleRaw.set(1.06);
    glowRaw.set(1);
  }, [scaleRaw, glowRaw]);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    scaleRaw.set(1);
    glowRaw.set(0);
    mouseX.set(0);
    mouseY.set(0);
  }, [scaleRaw, glowRaw, mouseX, mouseY]);

  const handleMouseDown = useCallback(() => {
    scaleRaw.set(0.92);
  }, [scaleRaw]);

  const handleMouseUp = useCallback(() => {
    scaleRaw.set(isHovered ? 1.06 : 1);
  }, [scaleRaw, isHovered]);

  function handleClick() {
    if (!state) setStateIndex((i) => (i + 1) % CYCLE.length);
  }

  return (
    <motion.div
      ref={containerRef}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      style={{
        cursor: 'pointer',
        x: offsetX,
        y: offsetY,
        scale,
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
        state={agentState}
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
          opacity: isHovered ? 1 : 0.6,
          y: isHovered ? -2 : 0,
        }}
        transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
      >
        {agentState}
      </motion.p>
    </motion.div>
  );
}
