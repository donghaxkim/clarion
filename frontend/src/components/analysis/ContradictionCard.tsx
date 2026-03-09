"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ContradictionItem } from "@/lib/types";

const SEVERITY_STYLES: Record<
  ContradictionItem["severity"],
  string
> = {
  high: "bg-danger/10 text-danger border-danger/25",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/25",
  low: "bg-surface-raised text-text-muted border-border",
};

interface ContradictionCardProps {
  contradiction: ContradictionItem;
  index: number;
}

export function ContradictionCard({ contradiction, index }: ContradictionCardProps) {
  const severityStyle = SEVERITY_STYLES[contradiction.severity];

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className="rounded bg-surface border border-border p-4 space-y-3"
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "px-2 py-0.5 rounded text-[10px] font-bold uppercase border",
            severityStyle
          )}
        >
          {contradiction.severity}
        </span>
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">
        {contradiction.description}
      </p>
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-start">
        <div className="rounded bg-surface-raised border border-border p-2.5 space-y-1">
          <p className="text-[11px] text-text-primary leading-snug">
            {contradiction.fact_a}
          </p>
          <p className="text-[10px] text-text-muted">
            {contradiction.source_a.detail}
          </p>
        </div>
        <span className="text-[10px] font-bold text-text-muted px-1 pt-2">
          vs
        </span>
        <div className="rounded bg-surface-raised border border-border p-2.5 space-y-1">
          <p className="text-[11px] text-text-primary leading-snug">
            {contradiction.fact_b}
          </p>
          <p className="text-[10px] text-text-muted">
            {contradiction.source_b.detail}
          </p>
        </div>
      </div>
    </motion.article>
  );
}
