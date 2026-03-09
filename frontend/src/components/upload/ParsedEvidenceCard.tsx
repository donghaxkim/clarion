"use client";

import { motion } from "framer-motion";
import {
  FileText,
  Image,
  Music,
  Video,
  Shield,
  User,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ParsedEvidence } from "@/lib/types";

interface ParsedEvidenceCardProps {
  evidence: ParsedEvidence;
  index: number;
}

function getFileIcon(filename: string, evidenceType: string) {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".mp4") || lower.endsWith(".mov")) return Video;
  if (lower.endsWith(".mp3") || lower.endsWith(".wav")) return Music;
  if (lower.endsWith(".jpg") || lower.endsWith(".png") || lower.endsWith(".jpeg")) return Image;
  if (evidenceType.toLowerCase().includes("police")) return Shield;
  if (evidenceType.toLowerCase().includes("witness") || evidenceType.toLowerCase().includes("statement")) return User;
  return FileText;
}

function getTypeBadgeStyle(evidenceType: string): string {
  const lower = evidenceType.toLowerCase();
  if (lower.includes("police") || lower.includes("official")) return "bg-indigo-500/10 text-indigo-400 border-indigo-500/25";
  if (lower.includes("witness") || lower.includes("statement")) return "bg-gold-500/10 text-gold-400 border-gold-500/25";
  if (lower.includes("medical")) return "bg-success/10 text-success border-success/25";
  if (lower.includes("video") || lower.includes("audio")) return "bg-amber-500/10 text-amber-400 border-amber-500/25";
  return "bg-surface-raised text-text-muted border-border";
}

export function ParsedEvidenceCard({ evidence, index }: ParsedEvidenceCardProps) {
  const Icon = getFileIcon(evidence.filename, evidence.evidence_type);
  const isParsed = evidence.status === "parsed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.35,
        delay: index * 0.1,
        ease: [0.16, 1, 0.3, 1],
      }}
      className="rounded bg-surface border border-border p-2.5 space-y-1.5"
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-surface-raised border border-border flex items-center justify-center flex-shrink-0">
            <Icon className="w-3 h-3 text-text-muted" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-text-primary truncate max-w-[140px]">
              {evidence.filename}
            </p>
            <span
              className={cn(
                "inline-flex items-center mt-0.5 px-1 py-0.5 rounded text-[9px] font-semibold uppercase border",
                getTypeBadgeStyle(evidence.evidence_type)
              )}
            >
              {evidence.evidence_type}
            </span>
          </div>
        </div>
        {isParsed ? (
          <CheckCircle className="w-3 h-3 text-success flex-shrink-0 mt-0.5" />
        ) : (
          <Loader2 className="w-3 h-3 text-gold-400 flex-shrink-0 mt-0.5 animate-spin" />
        )}
      </div>

      {/* Summary */}
      <p className="text-[10px] text-text-muted leading-snug line-clamp-2">
        {evidence.summary}
      </p>

      {/* Labels + entity count */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex flex-wrap gap-0.5">
          {evidence.labels.slice(0, 3).map((label) => (
            <span
              key={label}
              className="px-1 py-0.5 rounded text-[8px] font-medium bg-surface-raised text-text-muted border border-border"
            >
              {label}
            </span>
          ))}
        </div>
        {evidence.entities.length > 0 && (
          <span className="text-[9px] text-text-muted tabular-nums shrink-0">
            {evidence.entities.length}
          </span>
        )}
      </div>
    </motion.div>
  );
}
