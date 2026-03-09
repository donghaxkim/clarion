"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { AlertTriangle, FileSearch } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MockContradiction, MockEvidence, MockMissingInfo } from "@/lib/mock-case";

interface ContradictionRevealProps {
  contradictions: MockContradiction[];
  evidence: MockEvidence[];
  missingInfo: MockMissingInfo[];
  elapsedMs: number;
  onComplete: () => void;
}

type RevealStage =
  | "pulse"      // evidence cards glow
  | "collision"  // sentences fly to center
  | "split"      // contradiction cards appear
  | "gaps"       // missing info appears
  | "done";

export default function ContradictionReveal({
  contradictions,
  evidence,
  missingInfo,
  elapsedMs,
  onComplete,
}: ContradictionRevealProps) {
  const shouldReduceMotion = useReducedMotion();
  const [stage, setStage] = useState<RevealStage>("pulse");
  const [activeContradictionIndex, setActiveContradictionIndex] = useState(0);
  const [showAll, setShowAll] = useState(false);

  const elapsedSec = (elapsedMs / 1000).toFixed(1);

  useEffect(() => {
    if (shouldReduceMotion) {
      setStage("done");
      setShowAll(true);
      return;
    }

    const timers = [
      setTimeout(() => setStage("collision"), 800),
      setTimeout(() => setStage("split"), 1800),
      setTimeout(() => { setActiveContradictionIndex(1); }, 3200),
      setTimeout(() => setStage("gaps"), 4200),
      setTimeout(() => { setStage("done"); setShowAll(true); }, 5000),
    ];

    return () => timers.forEach(clearTimeout);
  }, [shouldReduceMotion]);

  const getEvidenceById = (id: string) => evidence.find((e) => e.id === id);

  const severityColor: Record<string, string> = {
    low: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    medium: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    high: "text-danger border-danger/30 bg-danger-muted",
    critical: "text-danger border-danger/30 bg-danger-muted",
    suggestion: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    warning: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  };

  return (
    <div className="space-y-6">
      {/* Timer badge */}
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="flex justify-center"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono bg-surface border border-border">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" aria-hidden="true" />
          Analysis complete in{" "}
          <span className="text-amber-400 font-semibold">{elapsedSec}s</span>
        </div>
      </motion.div>

      {/* Contradictions section */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-danger" aria-hidden="true" />
          <h3 className="font-semibold text-text-primary text-sm">
            Contradictions Detected
          </h3>
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-danger-muted text-danger border border-danger/20">
            {contradictions.length}
          </span>
        </div>

        <div className="space-y-4">
          {contradictions.map((c, idx) => {
            const evA = getEvidenceById(c.evidenceAId);
            const evB = getEvidenceById(c.evidenceBId);
            const isActive = idx <= activeContradictionIndex || showAll;

            return (
              <AnimatePresence key={c.id}>
                {isActive && (
                  <motion.div
                    initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 16, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] }}
                    className={cn(
                      "rounded-2xl border overflow-hidden shadow-glass",
                      "border-danger/20 bg-surface"
                    )}
                    role="alert"
                    aria-label={`Contradiction: ${c.label}`}
                  >
                    {/* Header */}
                    <div className="flex items-start gap-3 px-4 pt-4 pb-3 border-b border-border">
                      <div className="shrink-0 mt-0.5">
                        <span className={cn("text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border", severityColor[c.severity])}>
                          {c.severity}
                        </span>
                      </div>
                      <div>
                        <div className="font-semibold text-text-primary text-sm">{c.label}</div>
                        <div className="text-text-muted text-xs mt-0.5 leading-relaxed">{c.description}</div>
                      </div>
                    </div>

                    {/* Conflicting facts side by side */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-border">
                      {/* Fact A */}
                      <motion.div
                        layoutId={`${c.id}-fact-a`}
                        className="p-4"
                      >
                        <div className="flex items-center gap-1.5 mb-2">
                          <div className="w-2 h-2 rounded-full bg-indigo-500" aria-hidden="true" />
                          <span className="text-[10px] uppercase tracking-wider text-indigo-400 font-medium">
                            {evA?.label ?? c.source_a.detail}
                          </span>
                        </div>
                        <blockquote className="text-sm text-text-secondary leading-relaxed border-l-2 border-indigo-500/40 pl-3">
                          &ldquo;{c.conflictingTextA}&rdquo;
                        </blockquote>
                        <p className="text-[10px] text-text-muted mt-2">{c.source_a.detail}</p>
                      </motion.div>

                      {/* Fact B */}
                      <motion.div
                        layoutId={`${c.id}-fact-b`}
                        className="p-4"
                      >
                        <div className="flex items-center gap-1.5 mb-2">
                          <div className="w-2 h-2 rounded-full bg-danger" aria-hidden="true" />
                          <span className="text-[10px] uppercase tracking-wider text-danger font-medium">
                            {evB?.label ?? c.source_b.detail}
                          </span>
                        </div>
                        <blockquote className="text-sm text-text-secondary leading-relaxed border-l-2 border-danger/40 pl-3">
                          &ldquo;{c.conflictingTextB}&rdquo;
                        </blockquote>
                        <p className="text-[10px] text-text-muted mt-2">{c.source_b.detail}</p>
                      </motion.div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            );
          })}
        </div>
      </div>

      {/* Missing info section */}
      <AnimatePresence>
        {(stage === "gaps" || stage === "done") && (
          <motion.div
            initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FileSearch className="w-4 h-4 text-amber-400" aria-hidden="true" />
              <h3 className="font-semibold text-text-primary text-sm">
                Evidence Gaps
              </h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {missingInfo.length}
              </span>
            </div>

            <div className="space-y-3">
              {missingInfo.map((gap, i) => (
                <motion.div
                  key={gap.id}
                  initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1, duration: 0.4 }}
                  className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
                  role="alert"
                  aria-label={`Evidence gap: ${gap.severity} severity`}
                >
                  <div className="flex items-start gap-3">
                    <span className={cn("text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border shrink-0 mt-0.5", severityColor[gap.severity])}>
                      {gap.severity}
                    </span>
                    <div>
                      <p className="text-sm text-text-secondary leading-relaxed">
                        {gap.description}
                      </p>
                      <p className="text-xs text-amber-400/80 mt-2">
                        <span className="font-medium">Recommendation:</span>{" "}
                        {gap.recommendation}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA to show result card */}
      <AnimatePresence>
        {stage === "done" && (
          <motion.div
            initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-center pt-4"
          >
            <motion.button
              onClick={onComplete}
              whileHover={!shouldReduceMotion ? { scale: 1.03 } : {}}
              whileTap={!shouldReduceMotion ? { scale: 0.97 } : {}}
              className={cn(
                "inline-flex items-center gap-2 px-6 py-3.5 rounded-xl",
                "bg-amber-500 text-background font-bold text-sm",
                "hover:bg-amber-400 transition-all shadow-glow-amber",
                "min-h-[44px]"
              )}
              aria-label="View your shareable result card"
            >
              View & Share Results
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
