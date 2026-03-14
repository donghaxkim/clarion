'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface Point { x: number; y: number }
interface ThreadLine { from: Point; to: Point; id: string }

interface ThreadLinesProps {
  sourceRefs: React.RefObject<HTMLElement>[];
  containerRef: React.RefObject<HTMLElement>;
  active: boolean;
}

export function ThreadLines({ sourceRefs, containerRef, active }: ThreadLinesProps) {
  const [lines, setLines] = useState<ThreadLine[]>([]);
  const [svgSize, setSvgSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!active || sourceRefs.length < 2) return;

    const container = containerRef.current;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    setSvgSize({ width: containerRect.width, height: containerRect.height });

    const newLines: ThreadLine[] = [];
    for (let i = 0; i < sourceRefs.length - 1; i += 2) {
      const a = sourceRefs[i]?.current;
      const b = sourceRefs[i + 1]?.current;
      if (!a || !b) continue;

      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();

      newLines.push({
        id: `thread-${i}`,
        from: {
          x: ra.left - containerRect.left + ra.width / 2,
          y: ra.top - containerRect.top + ra.height / 2,
        },
        to: {
          x: rb.left - containerRect.left + rb.width / 2,
          y: rb.top - containerRect.top + rb.height / 2,
        },
      });
    }

    setLines(newLines);
  }, [active, sourceRefs, containerRef]);

  if (!active || lines.length === 0) return null;

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: svgSize.width,
        height: svgSize.height,
        pointerEvents: 'none',
        zIndex: 5,
      }}
    >
      {lines.map((line) => {
        const d = `M ${line.from.x} ${line.from.y} L ${line.to.x} ${line.to.y}`;
        return (
          <motion.path
            key={line.id}
            d={d}
            stroke="var(--accent)"
            strokeWidth="1"
            fill="none"
            initial={{ pathLength: 0, opacity: 0.9 }}
            animate={{ pathLength: 1, opacity: 0.15 }}
            transition={{
              pathLength: { duration: 1.2, ease: 'easeInOut' },
              opacity: { delay: 1.0, duration: 0.4 },
            }}
          />
        );
      })}
    </svg>
  );
}
