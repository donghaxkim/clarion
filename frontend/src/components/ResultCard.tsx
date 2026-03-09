"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Share2, ArrowRight, AlertTriangle, FileSearch, Zap } from "lucide-react";
import { cn, buildTwitterIntent } from "@/lib/utils";

interface ResultCardProps {
  contradictions: number;
  gaps: number;
  caseName: string;
  analysisTimeMs: number;
  confidenceScore: number;
  impactAssessment: "LOW" | "MEDIUM" | "HIGH";
  shareText: string;
  resultId: string;
}

const impactColors = {
  LOW: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  MEDIUM: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  HIGH: "text-danger bg-danger-muted border-danger/20",
};

export default function ResultCard({
  contradictions,
  gaps,
  caseName,
  analysisTimeMs,
  confidenceScore,
  impactAssessment,
  shareText,
  resultId,
}: ResultCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const analysisTimeSec = (analysisTimeMs / 1000).toFixed(1);

  const shareUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/result/${resultId}`
      : `https://clarion.ai/result/${resultId}`;

  const twitterUrl = buildTwitterIntent(shareText, shareUrl);

  const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 16 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] },
    },
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="max-w-2xl mx-auto space-y-4"
    >
      {/* The shareable card */}
      <motion.div
        variants={itemVariants}
        className="rounded-2xl border border-amber-500/30 bg-surface shadow-glass-amber overflow-hidden"
        id="result-card"
        aria-label="Analysis result card"
      >
        {/* Card header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-background/40">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" aria-hidden="true" />
            <span className="text-xs font-bold text-amber-400 tracking-wider uppercase">
              Clarion AI
            </span>
          </div>
          <span className="text-xs text-text-muted font-mono">
            {analysisTimeSec}s
          </span>
        </div>

        {/* Card body */}
        <div className="p-5 sm:p-6">
          <p className="text-xs text-text-muted mb-1 uppercase tracking-wider">
            Case Analysis
          </p>
          <h3 className="text-lg font-bold text-text-primary mb-5 leading-tight">
            {caseName}
          </h3>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3 mb-5">
            {/* Contradictions */}
            <div className="flex flex-col items-center text-center p-3 rounded-xl bg-danger-muted border border-danger/20">
              <AlertTriangle className="w-4 h-4 text-danger mb-1.5" aria-hidden="true" />
              <div className="text-3xl font-black text-danger tabular-nums">
                {contradictions}
              </div>
              <div className="text-[10px] text-danger/70 mt-0.5 leading-tight">
                contradictions
              </div>
            </div>

            {/* Evidence gaps */}
            <div className="flex flex-col items-center text-center p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <FileSearch className="w-4 h-4 text-amber-400 mb-1.5" aria-hidden="true" />
              <div className="text-3xl font-black text-amber-400 tabular-nums">
                {gaps}
              </div>
              <div className="text-[10px] text-amber-400/70 mt-0.5 leading-tight">
                evidence gaps
              </div>
            </div>

            {/* Confidence */}
            <div className="flex flex-col items-center text-center p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
              <div className="text-3xl font-black text-indigo-400 tabular-nums">
                {confidenceScore}%
              </div>
              <div className="text-[10px] text-indigo-400/70 mt-0.5 leading-tight">
                AI confidence
              </div>
            </div>
          </div>

          {/* Impact assessment */}
          <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-surface-raised border border-border">
            <span className="text-xs text-text-secondary font-medium">
              Case Outcome Risk
            </span>
            <span
              className={cn(
                "text-xs font-black uppercase tracking-wider px-3 py-1 rounded-full border",
                impactColors[impactAssessment]
              )}
            >
              {impactAssessment}
            </span>
          </div>
        </div>
      </motion.div>

      {/* Share CTA */}
      <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-3">
        <a
          href={twitterUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex-1 inline-flex items-center justify-center gap-2.5 px-5 py-3.5 rounded-xl",
            "bg-[#1D9BF0] text-white font-bold text-sm",
            "hover:bg-[#1a8cd8] active:scale-95 transition-all",
            "min-h-[44px]"
          )}
          aria-label="Share analysis on X (Twitter)"
        >
          <Share2 className="w-4 h-4" aria-hidden="true" />
          Share on X
        </a>
        <a
          href="#waitlist"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
          }}
          className={cn(
            "flex-1 inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl",
            "bg-amber-500 text-background font-bold text-sm",
            "hover:bg-amber-400 active:scale-95 transition-all shadow-glow-amber",
            "min-h-[44px]"
          )}
          aria-label="Get access to Clarion for your cases"
        >
          Get Access
          <ArrowRight className="w-4 h-4" aria-hidden="true" />
        </a>
      </motion.div>

      {/* Permalink */}
      <motion.p variants={itemVariants} className="text-center text-xs text-text-muted">
        Shareable link:{" "}
        <a
          href={`/result/${resultId}`}
          className="text-text-secondary hover:text-amber-400 transition-colors underline underline-offset-2"
        >
          clarion.ai/result/{resultId}
        </a>
      </motion.p>
    </motion.div>
  );
}
