'use client';

import { motion } from 'framer-motion';
import type { AgentState } from '@livekit/components-react';

export interface AgentAudioVisualizerAuraProps {
  state: AgentState;
  color?: string;
  colorShift?: number;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  themeMode?: 'light' | 'dark';
  className?: string;
}

const SIZE_MAP: Record<NonNullable<AgentAudioVisualizerAuraProps['size']>, string> = {
  sm: '48px',
  md: '64px',
  lg: '96px',
  xl: '100%',
};

interface RingConfig {
  scale: number[];
  opacity: number[];
  duration: number;
  delay?: number;
}

interface OrbConfig {
  scale: number[];
  opacity: number[];
  duration: number;
}

interface StateConfig {
  orb: OrbConfig;
  rings: RingConfig[];
  transition: 'loop' | 'static';
}

function getStateConfig(state: AgentState): StateConfig {
  switch (state) {
    case 'disconnected':
    case 'failed':
      return {
        orb: { scale: [1], opacity: [0.2], duration: 4 },
        rings: [
          { scale: [1, 1.05], opacity: [0.05, 0.02], duration: 4 },
          { scale: [1, 1.04], opacity: [0.03, 0.01], duration: 4, delay: 0.5 },
        ],
        transition: 'static',
      };

    case 'connecting':
    case 'initializing':
    case 'pre-connect-buffering':
      return {
        orb: { scale: [1, 1.04, 1], opacity: [0.5, 0.7, 0.5], duration: 2.5 },
        rings: [
          { scale: [1, 1.15, 1], opacity: [0.3, 0.1, 0.3], duration: 2.5 },
          { scale: [1, 1.2, 1], opacity: [0.2, 0.05, 0.2], duration: 2.5, delay: 0.8 },
        ],
        transition: 'loop',
      };

    case 'idle':
      return {
        orb: { scale: [1, 1.05, 1], opacity: [0.6, 0.75, 0.6], duration: 3.5 },
        rings: [
          { scale: [1, 1.12, 1], opacity: [0.35, 0.12, 0.35], duration: 3.5 },
          { scale: [1, 1.18, 1], opacity: [0.2, 0.05, 0.2], duration: 3.5, delay: 1 },
          { scale: [1, 1.25, 1], opacity: [0.1, 0.02, 0.1], duration: 3.5, delay: 1.8 },
        ],
        transition: 'loop',
      };

    case 'listening':
      return {
        orb: { scale: [1, 1.07, 1], opacity: [0.7, 0.9, 0.7], duration: 2 },
        rings: [
          { scale: [1, 1.2, 1], opacity: [0.5, 0.15, 0.5], duration: 2 },
          { scale: [1, 1.35, 1], opacity: [0.3, 0.06, 0.3], duration: 2, delay: 0.5 },
          { scale: [1, 1.5, 1], opacity: [0.15, 0.02, 0.15], duration: 2, delay: 1 },
        ],
        transition: 'loop',
      };

    case 'thinking':
      return {
        orb: { scale: [1, 1.06, 0.97, 1.06, 1], opacity: [0.7, 0.85, 0.65, 0.85, 0.7], duration: 1.5 },
        rings: [
          { scale: [1, 1.25, 0.95, 1.25, 1], opacity: [0.45, 0.1, 0.35, 0.1, 0.45], duration: 1.5 },
          { scale: [1, 1.4, 1, 1.4, 1], opacity: [0.25, 0.04, 0.2, 0.04, 0.25], duration: 1.5, delay: 0.3 },
          { scale: [1, 1.55, 1], opacity: [0.12, 0.02, 0.12], duration: 1.5, delay: 0.7 },
        ],
        transition: 'loop',
      };

    case 'speaking':
      return {
        orb: { scale: [1, 1.1, 0.97, 1.1, 1], opacity: [0.85, 1, 0.8, 1, 0.85], duration: 0.9 },
        rings: [
          { scale: [1, 1.3, 1], opacity: [0.65, 0.18, 0.65], duration: 0.9 },
          { scale: [1, 1.55, 1], opacity: [0.4, 0.07, 0.4], duration: 0.9, delay: 0.2 },
          { scale: [1, 1.8, 1], opacity: [0.2, 0.02, 0.2], duration: 0.9, delay: 0.45 },
        ],
        transition: 'loop',
      };

    default:
      return {
        orb: { scale: [1], opacity: [0.5], duration: 3 },
        rings: [
          { scale: [1, 1.1, 1], opacity: [0.25, 0.08, 0.25], duration: 3 },
        ],
        transition: 'loop',
      };
  }
}

export function AgentAudioVisualizerAura({
  state,
  color = '#1FD5F9',
  colorShift = 0,
  size = 'lg',
  themeMode = 'dark',
  className,
}: AgentAudioVisualizerAuraProps) {
  const config = getStateConfig(state);
  const containerSize = SIZE_MAP[size];
  const isXl = size === 'xl';

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    width: isXl ? '100%' : containerSize,
    height: isXl ? undefined : containerSize,
    aspectRatio: '1 / 1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const orbGlow = themeMode === 'light'
    ? `0 0 16px 6px ${color}55, 0 0 32px 10px ${color}22, inset 0 0 8px 2px #ffffff66`
    : `0 0 16px 6px ${color}66, 0 0 32px 10px ${color}33`;

  return (
    <div style={containerStyle} className={className}>
      {/* Rings */}
      {config.rings.map((ring, i) => {
        const isOuter = i >= 1;
        const hueFilter = isOuter && colorShift
          ? `hue-rotate(${colorShift * (i * 15)}deg)`
          : undefined;

        return (
          <motion.div
            key={i}
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: `1.5px solid ${color}`,
              filter: hueFilter,
            }}
            animate={{
              scale: config.rings[i].scale,
              opacity: config.rings[i].opacity,
            }}
            transition={{
              duration: ring.duration,
              delay: ring.delay ?? 0,
              repeat: config.transition === 'loop' ? Infinity : 0,
              ease: 'easeInOut',
            }}
          />
        );
      })}

      {/* Central orb */}
      <motion.div
        style={{
          position: 'absolute',
          width: '40%',
          height: '40%',
          borderRadius: '50%',
          backgroundColor: color,
          boxShadow: orbGlow,
        }}
        animate={{
          scale: config.orb.scale,
          opacity: config.orb.opacity,
        }}
        transition={{
          duration: config.orb.duration,
          repeat: config.transition === 'loop' ? Infinity : 0,
          ease: 'easeInOut',
        }}
      />
    </div>
  );
}
