"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { TimelineEvent } from "@/lib/types";

interface TimelineBlockProps {
  events: TimelineEvent[];
  content?: string;
  onEventClick?: (event: TimelineEvent) => void;
  highlightedSectionId?: string | null;
}

export function TimelineBlock({
  events,
  content,
  onEventClick,
  highlightedSectionId,
}: TimelineBlockProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div className="my-6">
      {content && (
        <p className="text-xs text-text-muted mb-4">{content}</p>
      )}
      <div
        ref={scrollRef}
        className="overflow-x-auto pb-4 -mx-2"
        style={{ scrollbarGutter: "stable" }}
      >
        <div className="flex items-start gap-0 min-w-max px-4">
          {events.map((evt, i) => {
            const isAbove = i % 2 === 0;
            const isHighlighted =
              highlightedSectionId != null && evt.section_id === highlightedSectionId;
            const isHovered = hoveredId === evt.id;

            return (
              <div
                key={evt.id}
                className="flex flex-col items-center flex-shrink-0"
                style={{ width: 140 }}
              >
                {isAbove && (
                  <div className="h-12 flex flex-col items-center justify-end mb-2">
                    <span className="text-[10px] font-semibold text-text-muted text-center">
                      {evt.timestamp}
                    </span>
                    <button
                      type="button"
                      onClick={() => onEventClick?.(evt)}
                      onMouseEnter={() => setHoveredId(evt.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      className={cn(
                        "mt-1 text-[11px] font-medium text-center px-2 py-1 rounded border transition-colors",
                        (isHighlighted || isHovered)
                          ? "bg-gold-500/15 border-gold-500/40 text-gold-400"
                          : "border-border text-text-secondary hover:border-gold-500/30"
                      )}
                    >
                      {evt.label}
                    </button>
                  </div>
                )}
                <div className="flex items-center gap-0">
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full border-2 flex-shrink-0 transition-colors",
                      isHighlighted || isHovered
                        ? "bg-gold-500 border-gold-400"
                        : "bg-surface-raised border-border"
                    )}
                  />
                  {i < events.length - 1 && (
                    <div
                      className={cn(
                        "h-0.5 w-[calc(140px-12px)] flex-shrink-0",
                        isHighlighted || isHovered
                          ? "bg-gold-500/40"
                          : "bg-border"
                      )}
                    />
                  )}
                </div>
                {!isAbove && (
                  <div className="h-12 flex flex-col items-center justify-start mt-2">
                    <span className="text-[10px] font-semibold text-text-muted text-center">
                      {evt.timestamp}
                    </span>
                    <button
                      type="button"
                      onClick={() => onEventClick?.(evt)}
                      onMouseEnter={() => setHoveredId(evt.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      className={cn(
                        "mt-1 text-[11px] font-medium text-center px-2 py-1 rounded border transition-colors",
                        (isHighlighted || isHovered)
                          ? "bg-gold-500/15 border-gold-500/40 text-gold-400"
                          : "border-border text-text-secondary hover:border-gold-500/30"
                      )}
                    >
                      {evt.label}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
