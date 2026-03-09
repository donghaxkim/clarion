"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { MissingInfoItem } from "@/lib/types";

const SEVERITY_STYLES: Record<
  MissingInfoItem["severity"],
  string
> = {
  critical: "bg-danger/10 text-danger border-danger/25",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/25",
  suggestion: "bg-surface-raised text-text-muted border-border",
};

interface MissingInfoCardProps {
  item: MissingInfoItem;
  index: number;
}

export function MissingInfoCard({ item, index }: MissingInfoCardProps) {
  const severityStyle = SEVERITY_STYLES[item.severity];

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className="rounded bg-surface border border-border p-3.5 space-y-2.5"
    >
      <span
        className={cn(
          "inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase border",
          severityStyle
        )}
      >
        {item.severity}
      </span>
      <p className="text-xs text-text-secondary leading-relaxed">
        {item.description}
      </p>
      <p className="text-[11px] text-text-muted italic leading-relaxed border-l-2 border-gold-500/30 pl-2.5">
        {item.recommendation}
      </p>
    </motion.article>
  );
}
