"use client";

import { motion } from "framer-motion";
import { FileText, User, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MockEvidence } from "@/lib/mock-case";

const ICONS = {
  "file-text": FileText,
  user: User,
  shield: Shield,
};

interface EvidenceCardProps {
  evidence: MockEvidence;
  isHighlighted: boolean;
  highlightedTexts?: string[];
  layoutIdPrefix?: string;
  isHidden?: boolean; // Mounted but visually hidden during contradiction reveal
  animationDelay?: number;
}

export default function EvidenceCard({
  evidence,
  isHighlighted,
  highlightedTexts = [],
  layoutIdPrefix = "",
  isHidden = false,
  animationDelay = 0,
}: EvidenceCardProps) {
  const Icon = ICONS[evidence.icon];

  // Build excerpt with highlights
  const renderExcerpt = () => {
    if (!isHighlighted || highlightedTexts.length === 0) {
      return <span className="text-text-muted text-xs leading-relaxed">{evidence.excerpt}</span>;
    }

    let text = evidence.excerpt;
    const parts: Array<{ text: string; highlighted: boolean; index: number }> = [];
    let cursor = 0;

    // Find all highlighted spans in order
    const matches: Array<{ start: number; end: number; matchText: string; matchIndex: number }> = [];
    highlightedTexts.forEach((ht, htIdx) => {
      const idx = text.indexOf(ht);
      if (idx !== -1) {
        matches.push({ start: idx, end: idx + ht.length, matchText: ht, matchIndex: htIdx });
      }
    });
    matches.sort((a, b) => a.start - b.start);

    matches.forEach(({ start, end, matchText, matchIndex }) => {
      if (cursor < start) {
        parts.push({ text: text.slice(cursor, start), highlighted: false, index: cursor });
      }
      parts.push({ text: matchText, highlighted: true, index: matchIndex });
      cursor = end;
    });
    if (cursor < text.length) {
      parts.push({ text: text.slice(cursor), highlighted: false, index: cursor });
    }

    return (
      <span className="text-xs leading-relaxed">
        {parts.map((part, i) =>
          part.highlighted ? (
            <motion.span
              key={`${layoutIdPrefix}-highlight-${part.index}`}
              layoutId={`${layoutIdPrefix}-sentence-${part.index}`}
              className="text-amber-400 font-medium animate-pulse-amber rounded px-0.5"
            >
              {part.text}
            </motion.span>
          ) : (
            <span key={i} className="text-text-muted">
              {part.text}
            </span>
          )
        )}
      </span>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={isHidden ? { opacity: 0 } : { opacity: 1, y: 0 }}
      transition={{ delay: animationDelay, duration: 0.4 }}
      className={cn(
        "relative rounded-2xl border p-4 transition-all duration-300 flex flex-col gap-3",
        isHighlighted
          ? "border-amber-500/40 bg-surface shadow-glass-amber"
          : "border-border bg-surface shadow-glass"
      )}
      aria-label={`Evidence: ${evidence.label}`}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "p-2 rounded-lg shrink-0",
            isHighlighted ? "bg-amber-500/10" : "bg-surface-raised"
          )}
        >
          <Icon
            className={cn(
              "w-4 h-4",
              isHighlighted ? "text-amber-400" : "text-text-secondary"
            )}
            aria-hidden="true"
          />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-text-primary text-sm truncate">
            {evidence.label}
          </div>
          <div className="text-text-muted text-xs truncate mt-0.5">
            {evidence.filename}
          </div>
        </div>
      </div>

      {/* Excerpt */}
      <div
        className={cn(
          "rounded-lg p-3 text-xs",
          isHighlighted ? "bg-amber-500/5 border border-amber-500/10" : "bg-background/40"
        )}
      >
        <div className="text-text-muted text-[10px] uppercase tracking-wider mb-1.5">
          Excerpt · Page {evidence.page}
        </div>
        {renderExcerpt()}
      </div>

      {/* Type badge */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-text-muted px-2 py-0.5 rounded-full border border-border bg-surface-raised">
          {evidence.type.replace(/_/g, " ")}
        </span>
        {isHighlighted && (
          <span className="text-[10px] text-amber-400 font-medium animate-pulse">
            ● Contradiction detected
          </span>
        )}
      </div>
    </motion.div>
  );
}
