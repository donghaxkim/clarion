"use client";

import { useReducer, useEffect, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Play, ChevronRight, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { MOCK_CASE, ANALYSIS_LOG_LINES } from "@/lib/mock-case";
import EvidenceCard from "@/components/EvidenceCard";
import ContradictionReveal from "@/components/ContradictionReveal";
import ResultCard from "@/components/ResultCard";

type DemoPhase =
  | "select"
  | "loading"
  | "ready"
  | "analyzing"
  | "revealing"
  | "result";

interface DemoState {
  phase: DemoPhase;
  progress: number;
  logLines: string[];
  elapsedMs: number;
}

type Action =
  | { type: "SELECT_CASE" }
  | { type: "EVIDENCE_LOADED" }
  | { type: "START_ANALYSIS" }
  | { type: "UPDATE_PROGRESS"; progress: number; logLine?: string }
  | { type: "ANALYSIS_DONE" }
  | { type: "REVEAL_DONE" }
  | { type: "SET_ELAPSED"; ms: number };

function reducer(state: DemoState, action: Action): DemoState {
  switch (action.type) {
    case "SELECT_CASE":
      return { ...state, phase: "loading" };
    case "EVIDENCE_LOADED":
      return { ...state, phase: "ready" };
    case "START_ANALYSIS":
      return { ...state, phase: "analyzing", progress: 0, logLines: [] };
    case "UPDATE_PROGRESS":
      return {
        ...state,
        progress: action.progress,
        logLines: action.logLine
          ? [...state.logLines, action.logLine]
          : state.logLines,
      };
    case "ANALYSIS_DONE":
      return { ...state, phase: "revealing", progress: 100 };
    case "REVEAL_DONE":
      return { ...state, phase: "result" };
    case "SET_ELAPSED":
      return { ...state, elapsedMs: action.ms };
    default:
      return state;
  }
}

const CASE_OPTIONS = [
  {
    id: "bus-accident",
    label: "Bus Accident",
    title: "Johnson v. Metro Transit Authority",
    description: "Personal injury — public transit collision",
    available: true,
  },
  {
    id: "medical",
    label: "Medical Malpractice",
    title: "Coming soon",
    description: "Surgical error with conflicting records",
    available: false,
  },
  {
    id: "employment",
    label: "Employment Dispute",
    title: "Coming soon",
    description: "Wrongful termination with HR documentation",
    available: false,
  },
];

const STEPS = ["Select Case", "Review Evidence", "AI Analysis", "Results"];

export default function DemoFlow() {
  const shouldReduceMotion = useReducedMotion();
  const [state, dispatch] = useReducer(reducer, {
    phase: "select",
    progress: 0,
    logLines: [],
    elapsedMs: 0,
  });

  const analysisStartRef = useRef<number>(0);
  const announcerRef = useRef<HTMLDivElement>(null);

  const currentStep =
    state.phase === "select"
      ? 0
      : state.phase === "loading" || state.phase === "ready"
      ? 1
      : state.phase === "analyzing"
      ? 2
      : 3;

  const announce = (msg: string) => {
    if (announcerRef.current) announcerRef.current.textContent = msg;
  };

  // Auto-advance from loading → ready
  useEffect(() => {
    if (state.phase === "loading") {
      const t = setTimeout(() => {
        dispatch({ type: "EVIDENCE_LOADED" });
        announce("Evidence loaded. Ready to analyze.");
      }, shouldReduceMotion ? 100 : 900);
      return () => clearTimeout(t);
    }
  }, [state.phase, shouldReduceMotion]);

  // Analysis simulation
  useEffect(() => {
    if (state.phase !== "analyzing") return;
    analysisStartRef.current = performance.now();

    const steps = shouldReduceMotion
      ? [
          { delay: 0, progress: 100, line: ANALYSIS_LOG_LINES[6] },
        ]
      : [
          { delay: 300, progress: 18, line: ANALYSIS_LOG_LINES[0] },
          { delay: 750, progress: 37, line: ANALYSIS_LOG_LINES[1] },
          { delay: 1200, progress: 55, line: ANALYSIS_LOG_LINES[2] },
          { delay: 1700, progress: 72, line: ANALYSIS_LOG_LINES[3] },
          { delay: 2100, progress: 87, line: ANALYSIS_LOG_LINES[4] },
          { delay: 2500, progress: 95, line: ANALYSIS_LOG_LINES[5] },
          { delay: 2900, progress: 100, line: ANALYSIS_LOG_LINES[6] },
        ];

    const timers = steps.map(({ delay, progress, line }) =>
      setTimeout(() => {
        dispatch({ type: "UPDATE_PROGRESS", progress, logLine: line });
        if (progress === 100) {
          dispatch({ type: "SET_ELAPSED", ms: performance.now() - analysisStartRef.current });
          setTimeout(() => dispatch({ type: "ANALYSIS_DONE" }), shouldReduceMotion ? 0 : 400);
        }
      }, delay)
    );

    return () => timers.forEach(clearTimeout);
  }, [state.phase, shouldReduceMotion]);

  return (
    <div className="max-w-5xl mx-auto px-4">
      {/* ARIA live region */}
      <div
        ref={announcerRef}
        role="status"
        aria-live="polite"
        className="sr-only"
      />

      {/* Section header */}
      <div className="text-center mb-10">
        <h2 className="text-2xl sm:text-3xl font-bold text-text-primary mb-2 tracking-tight">
          Watch it work
        </h2>
        <p className="text-text-secondary text-sm">
          An interactive demo — no account required.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-center gap-0 mb-10 max-w-sm mx-auto" aria-label="Progress steps">
        {STEPS.map((step, i) => (
          <div key={step} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
                  i < currentStep
                    ? "bg-amber-500 text-background"
                    : i === currentStep
                    ? "bg-amber-500/20 border-2 border-amber-500 text-amber-400"
                    : "bg-surface border border-border text-text-muted"
                )}
                aria-current={i === currentStep ? "step" : undefined}
              >
                {i < currentStep ? "✓" : i + 1}
              </div>
              <span
                className={cn(
                  "text-[10px] hidden sm:block whitespace-nowrap",
                  i === currentStep ? "text-amber-400" : "text-text-muted"
                )}
              >
                {step}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "w-10 sm:w-16 h-px mx-1 transition-colors duration-500",
                  i < currentStep ? "bg-amber-500" : "bg-border"
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Phase content */}
      <AnimatePresence mode="wait">
        {/* STEP 1: Select */}
        {state.phase === "select" && (
          <motion.div
            key="select"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
          >
            <p className="text-center text-text-secondary text-sm mb-6">
              Choose a case to analyze:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {CASE_OPTIONS.map((opt) => (
                <motion.button
                  key={opt.id}
                  onClick={() => {
                    if (!opt.available) return;
                    dispatch({ type: "SELECT_CASE" });
                    announce("Loading evidence documents...");
                  }}
                  disabled={!opt.available}
                  whileHover={opt.available && !shouldReduceMotion ? { scale: 1.02, y: -2 } : {}}
                  whileTap={opt.available && !shouldReduceMotion ? { scale: 0.98 } : {}}
                  className={cn(
                    "relative flex flex-col items-start gap-2 p-5 rounded-2xl border text-left transition-all duration-200",
                    opt.available
                      ? "border-border bg-surface hover:border-amber-500/40 hover:shadow-glass-amber cursor-pointer"
                      : "border-border bg-surface opacity-40 cursor-not-allowed"
                  )}
                  aria-label={opt.available ? `Select ${opt.title}` : `${opt.label} — coming soon`}
                >
                  {!opt.available && (
                    <div className="absolute top-3 right-3">
                      <Lock className="w-3.5 h-3.5 text-text-muted" aria-hidden="true" />
                    </div>
                  )}
                  <span className="text-xs font-medium text-amber-400 uppercase tracking-wider">
                    {opt.label}
                  </span>
                  <span className="font-semibold text-text-primary text-sm leading-tight">
                    {opt.title}
                  </span>
                  <span className="text-xs text-text-muted">{opt.description}</span>
                  {opt.available && (
                    <div className="flex items-center gap-1 mt-2 text-amber-400 text-xs font-medium">
                      <Play className="w-3 h-3" aria-hidden="true" />
                      Run demo
                    </div>
                  )}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        {/* STEP 2: Evidence loaded */}
        {(state.phase === "loading" || state.phase === "ready") && (
          <motion.div
            key="evidence"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
          >
            <div className="mb-4 text-center">
              <span className="text-sm text-text-secondary">
                <span className="text-amber-400 font-medium">Johnson v. Metro Transit</span>
                {" "}· 3 evidence documents
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              {MOCK_CASE.evidence.map((ev, i) => (
                <EvidenceCard
                  key={ev.id}
                  evidence={ev}
                  isHighlighted={false}
                  animationDelay={shouldReduceMotion ? 0 : i * 0.15}
                />
              ))}
            </div>
            <div className="text-center">
              <motion.button
                onClick={() => {
                  dispatch({ type: "START_ANALYSIS" });
                  announce("Analyzing evidence with AI...");
                }}
                initial={{ opacity: 0, y: 10 }}
                animate={state.phase === "ready" ? { opacity: 1, y: 0 } : { opacity: 0 }}
                transition={{ duration: shouldReduceMotion ? 0 : 0.4 }}
                whileHover={!shouldReduceMotion ? { scale: 1.03 } : {}}
                whileTap={!shouldReduceMotion ? { scale: 0.97 } : {}}
                className={cn(
                  "inline-flex items-center gap-2.5 px-8 py-4 rounded-2xl",
                  "bg-amber-500 text-background font-bold text-base",
                  "hover:bg-amber-400 transition-all shadow-glow-amber",
                  "min-h-[44px]",
                  state.phase !== "ready" && "pointer-events-none"
                )}
                aria-label="Analyze evidence with AI"
              >
                <Play className="w-5 h-5" aria-hidden="true" />
                Analyze with AI
              </motion.button>
            </div>
          </motion.div>
        )}

        {/* STEP 3: Analyzing */}
        {state.phase === "analyzing" && (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
            className="max-w-2xl mx-auto"
          >
            <div className="rounded-2xl border border-border bg-surface shadow-glass overflow-hidden">
              {/* Terminal header */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-background/40">
                <div className="w-3 h-3 rounded-full bg-danger/60" />
                <div className="w-3 h-3 rounded-full bg-amber-500/60" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
                <span className="ml-2 text-xs text-text-muted font-mono">
                  clarion-ai — analysis
                </span>
              </div>

              {/* Progress bar */}
              <div className="px-4 pt-4 pb-2">
                <div className="h-1.5 bg-surface-raised rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-amber-600 to-amber-400 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${state.progress}%` }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[10px] text-text-muted font-mono">progress</span>
                  <span className="text-[10px] text-amber-400 font-mono tabular-nums">
                    {state.progress}%
                  </span>
                </div>
              </div>

              {/* Log lines */}
              <div className="px-4 pb-4 min-h-[160px] font-mono text-xs space-y-1.5">
                {state.logLines.map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25 }}
                    className="text-amber-400/80"
                  >
                    <span className="text-text-muted mr-2">›</span>
                    {line}
                  </motion.div>
                ))}
                {state.progress < 100 && (
                  <span className="inline-block w-2 h-3.5 bg-amber-400 animate-blink" aria-hidden="true" />
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* STEP 4: Contradiction reveal */}
        {state.phase === "revealing" && (
          <motion.div
            key="revealing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
          >
            <ContradictionReveal
              contradictions={MOCK_CASE.contradictions}
              evidence={MOCK_CASE.evidence}
              missingInfo={MOCK_CASE.missingInfo}
              elapsedMs={state.elapsedMs || MOCK_CASE.analysisTimeMs}
              onComplete={() => {
                dispatch({ type: "REVEAL_DONE" });
                announce("Analysis complete. 2 contradictions and 1 evidence gap found.");
              }}
            />
          </motion.div>
        )}

        {/* STEP 5: Result */}
        {state.phase === "result" && (
          <motion.div
            key="result"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.4 }}
          >
            <ResultCard
              contradictions={MOCK_CASE.result.contradictionCount}
              gaps={MOCK_CASE.result.gapCount}
              caseName={MOCK_CASE.title}
              analysisTimeMs={state.elapsedMs || MOCK_CASE.analysisTimeMs}
              confidenceScore={MOCK_CASE.result.confidenceScore}
              impactAssessment={MOCK_CASE.result.impactAssessment}
              shareText={MOCK_CASE.result.shareText}
              resultId={MOCK_CASE.id}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
