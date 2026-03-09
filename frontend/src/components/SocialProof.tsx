"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { Scale, Clock, TrendingUp } from "lucide-react";
import { SOCIAL_PROOF } from "@/lib/mock-case";
import { formatNumber } from "@/lib/utils";

function useCountUp(end: number, duration: number = 1500, enabled: boolean = true) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setCount(end);
      return;
    }
    let start = 0;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(start + (end - start) * eased));
      if (progress < 1) requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
  }, [end, duration, enabled]);

  return count;
}

const stats = [
  {
    icon: Scale,
    value: SOCIAL_PROOF.casesAnalyzed,
    label: "Cases Analyzed",
    suffix: "",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
  {
    icon: Clock,
    value: 32,
    label: "Avg. Analysis Time",
    suffix: "s",
    color: "text-indigo-400",
    bgColor: "bg-indigo-500/10",
  },
  {
    icon: TrendingUp,
    value: SOCIAL_PROOF.legalTeams,
    label: "Legal Teams",
    suffix: "+",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
  },
];

const useCases = [
  { type: "Personal Injury", detail: "3 contradictions found across 5 documents" },
  { type: "Employment Dispute", detail: "Missing witness statement identified" },
  { type: "Medical Malpractice", detail: "Timeline inconsistency in records exposed" },
  { type: "Insurance Fraud", detail: "2 conflicting damage assessments detected" },
];

export default function SocialProof() {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  const shouldReduceMotion = useReducedMotion();

  const caseCount = useCountUp(SOCIAL_PROOF.casesAnalyzed, 1500, isInView && !shouldReduceMotion);
  const timeCount = useCountUp(32, 800, isInView && !shouldReduceMotion);
  const teamCount = useCountUp(SOCIAL_PROOF.legalTeams, 1000, isInView && !shouldReduceMotion);

  const values = [
    shouldReduceMotion ? SOCIAL_PROOF.casesAnalyzed : caseCount,
    shouldReduceMotion ? 32 : timeCount,
    shouldReduceMotion ? SOCIAL_PROOF.legalTeams : teamCount,
  ];

  return (
    <div ref={ref} className="max-w-5xl mx-auto px-4">
      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-16">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              className="flex flex-col items-center text-center p-6 rounded-2xl bg-surface border border-border shadow-glass"
            >
              <div className={`p-2.5 rounded-xl ${stat.bgColor} mb-4`}>
                <Icon className={`w-5 h-5 ${stat.color}`} aria-hidden="true" />
              </div>
              <div className={`text-4xl font-bold tabular-nums ${stat.color} mb-1`}>
                {formatNumber(values[i])}
                {stat.suffix}
              </div>
              <div className="text-sm text-text-muted">{stat.label}</div>
            </motion.div>
          );
        })}
      </div>

      {/* Recent cases ticker */}
      <div className="text-center mb-6">
        <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest mb-6">
          Recent Analyses
        </h3>
        <div className="flex flex-col gap-2 max-w-lg mx-auto">
          {useCases.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -16 }}
              animate={isInView ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: 0.3 + i * 0.08, duration: 0.4 }}
              className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-surface border border-border text-sm"
            >
              <span className="font-medium text-text-secondary">{item.type}</span>
              <span className="text-text-muted text-xs">{item.detail}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
