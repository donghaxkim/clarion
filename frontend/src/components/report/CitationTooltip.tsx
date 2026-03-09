"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import type { Citation } from "@/lib/types";

interface CitationTooltipProps {
  citationId: string;
  index: number;
  citations: Record<string, Citation>;
  children?: React.ReactNode;
}

export function CitationTooltip({
  citationId,
  index,
  citations,
  children,
}: CitationTooltipProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  const citation = citations[citationId];
  const label = citation
    ? citation.filename +
      (citation.page != null ? `, p.${citation.page}` : "") +
      (citation.timestamp ? ` @ ${citation.timestamp}` : "")
    : "";
  const excerpt = citation?.excerpt ?? "";

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex">
      <sup
        role="button"
        tabIndex={0}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={cn(
          "inline-flex items-center justify-center min-w-[1.25em] h-4 px-0.5 rounded",
          "bg-gold-500/15 text-gold-400 text-[10px] font-semibold cursor-help",
          "hover:bg-gold-500/25 transition-colors"
        )}
      >
        {children ?? index}
      </sup>
      {open && (citation || citationId) && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-72 max-w-[90vw] rounded border border-border bg-surface-raised p-3 shadow-lg"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <p className="text-[10px] font-semibold text-gold-400 truncate">
            {label}
          </p>
          <p className="text-xs text-text-secondary mt-1 leading-relaxed line-clamp-3">
            {excerpt}
          </p>
        </div>
      )}
    </span>
  );
}

/** Parse content string with [1], [2] markers and return segments + citation indices */
export function parseContentWithCitations(
  content: string,
  citationIds: string[] = []
): Array<{ type: "text"; value: string } | { type: "citation"; index: number; id: string }> {
  const parts: Array<{ type: "text"; value: string } | { type: "citation"; index: number; id: string }> = [];
  const re = /\[(\d+)\]/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ type: "text", value: content.slice(lastIndex, m.index) });
    }
    const num = parseInt(m[1], 10);
    const id = citationIds[num - 1] ?? `cite-${num}`;
    parts.push({ type: "citation", index: num, id });
    lastIndex = re.lastIndex;
  }
  if (lastIndex < content.length) {
    parts.push({ type: "text", value: content.slice(lastIndex) });
  }
  return parts;
}
