"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ArrowRight, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { SOCIAL_PROOF } from "@/lib/mock-case";

const MORPHING_WORDS = ["contradictions", "evidence gaps", "blind spots", "case weaknesses"];

export default function Hero() {
  const [wordIndex, setWordIndex] = useState(0);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (shouldReduceMotion) return;
    const interval = setInterval(() => {
      setWordIndex((i) => (i + 1) % MORPHING_WORDS.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [shouldReduceMotion]);

  const containerVariants = {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.12 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 24 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.21, 0.47, 0.32, 0.98] } },
  };

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-4 pt-20 pb-12 overflow-hidden">
      {/* Mesh gradient background */}
      <div
        className="absolute inset-0 bg-mesh-amber pointer-events-none"
        aria-hidden="true"
      />

      {/* Radial vignette */}
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_30%,#0A0A0F_80%)] pointer-events-none"
        aria-hidden="true"
      />

      <motion.div
        className="relative z-10 max-w-4xl mx-auto text-center"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Badge */}
        <motion.div variants={itemVariants} className="mb-6 flex justify-center">
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Zap className="w-3 h-3" aria-hidden="true" />
            AI-Powered Litigation Analysis
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          variants={itemVariants}
          className="text-4xl sm:text-5xl md:text-display-lg lg:text-display-xl font-bold tracking-tight text-text-primary leading-[1.1] mb-4"
        >
          AI that finds legal
          <br />
          <span className="relative inline-block" aria-live="polite" aria-atomic="true">
            <AnimatePresence mode="wait">
              <motion.span
                key={wordIndex}
                initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="text-amber-500 block"
              >
                {MORPHING_WORDS[wordIndex]}
              </motion.span>
            </AnimatePresence>
          </span>
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          variants={itemVariants}
          className="text-base sm:text-lg text-text-secondary max-w-2xl mx-auto mb-10 leading-relaxed"
        >
          Upload evidence. In seconds, Clarion cross-references every document,
          statement, and record — surfacing contradictions and gaps your
          opponents will exploit before you do.
        </motion.p>

        {/* CTA */}
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="#demo"
            className={cn(
              "inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl",
              "bg-amber-500 text-background font-semibold text-sm",
              "hover:bg-amber-400 active:scale-95 transition-all duration-150",
              "shadow-glow-amber min-h-[44px] min-w-[44px]"
            )}
          >
            See the Demo
            <ArrowRight className="w-4 h-4" aria-hidden="true" />
          </a>
          <a
            href="#waitlist"
            className={cn(
              "inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl",
              "bg-surface border border-border text-text-primary font-medium text-sm",
              "hover:border-border-bright hover:bg-surface-raised active:scale-95 transition-all duration-150",
              "min-h-[44px] min-w-[44px]"
            )}
          >
            Join the Waitlist
          </a>
        </motion.div>

        {/* Social proof */}
        <motion.p
          variants={itemVariants}
          className="mt-8 text-sm text-text-muted"
        >
          Join{" "}
          <span className="text-text-secondary font-medium">
            {SOCIAL_PROOF.legalTeams}+ legal teams
          </span>{" "}
          already using Clarion ·{" "}
          <span className="text-text-secondary font-medium">
            {SOCIAL_PROOF.casesAnalyzed.toLocaleString()} cases analyzed
          </span>
        </motion.p>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 0.6 }}
        aria-hidden="true"
      >
        <div className="flex flex-col items-center gap-1">
          <div className="w-px h-8 bg-gradient-to-b from-transparent to-border" />
          <div className="w-1.5 h-1.5 rounded-full bg-border-bright" />
        </div>
      </motion.div>
    </section>
  );
}
