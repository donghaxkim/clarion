"use client";

import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  CitationTooltip,
  parseContentWithCitations,
} from "./CitationTooltip";
import { TimelineBlock } from "./TimelineBlock";
import type { ReportSection, Citation, ContradictionItem } from "@/lib/types";

interface ReportBlockProps {
  section: ReportSection;
  citations: Record<string, Citation>;
  contradictions?: ContradictionItem[];
  onContradictionClick?: (id: string) => void;
  onEditClick?: (sectionId: string) => void;
}

export function ReportBlock({
  section,
  citations,
  contradictions = [],
  onContradictionClick,
  onEditClick,
}: ReportBlockProps) {
  const { section_id, block_type, heading_level, content, citation_ids = [], contradiction_ids = [] } = section;
  const sectionContradictions = contradiction_ids
    .map((id) => contradictions.find((c) => c.id === id))
    .filter(Boolean) as ContradictionItem[];

  if (block_type === "heading") {
    const Tag = `h${Math.min(3, heading_level ?? 1)}` as "h1" | "h2" | "h3";
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-8 first:mt-0"
      >
        <Tag
          className={cn(
            "font-display text-text-primary",
            Tag === "h1" && "text-2xl font-bold",
            Tag === "h2" && "text-xl font-semibold",
            Tag === "h3" && "text-lg font-medium"
          )}
        >
          {content}
        </Tag>
      </motion.div>
    );
  }

  if (block_type === "text") {
    const parts = parseContentWithCitations(content, citation_ids);
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative group mt-4"
      >
        <p className="text-sm text-text-secondary leading-relaxed">
          {parts.map((part, i) =>
            part.type === "text" ? (
              <span key={i}>{part.value}</span>
            ) : (
              <CitationTooltip
                key={i}
                citationId={part.id}
                index={part.index}
                citations={citations}
              />
            )
          )}
        </p>
        {sectionContradictions.length > 0 && (
          <button
            type="button"
            onClick={() => onContradictionClick?.(sectionContradictions[0].id)}
            className="absolute -left-6 top-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-amber-500/10"
            title="View contradiction"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          </button>
        )}
        {onEditClick && (
          <button
            type="button"
            onClick={() => onEditClick(section_id)}
            className="absolute -right-2 top-0 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] text-text-muted hover:text-gold-400"
          >
            Edit
          </button>
        )}
      </motion.div>
    );
  }

  if (block_type === "counter_argument") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded border border-danger/20 bg-danger/5 p-4"
      >
        <p className="text-[10px] font-bold uppercase text-danger/90 mb-2">
          ⚔️ Opposing View
        </p>
        <p className="text-sm text-text-secondary leading-relaxed">
          {content}
        </p>
      </motion.div>
    );
  }

  if (block_type === "timeline" && section.events?.length) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <TimelineBlock events={section.events} content={content} />
      </motion.div>
    );
  }

  if (block_type === "image" || block_type === "evidence_image") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded border border-border overflow-hidden"
      >
        {section.image_url ? (
          <img
            src={section.image_url}
            alt={content || "Evidence"}
            className="w-full h-auto"
          />
        ) : (
          <div className="aspect-video bg-surface-raised flex items-center justify-center text-text-muted text-xs">
            [Image: {content || "Evidence"}]
          </div>
        )}
      </motion.div>
    );
  }

  if (block_type === "video") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded border border-border overflow-hidden bg-surface-raised aspect-video flex items-center justify-center text-text-muted text-xs"
      >
        [Video: {content || "Evidence"}]
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4 text-sm text-text-secondary"
    >
      {content}
    </motion.div>
  );
}
