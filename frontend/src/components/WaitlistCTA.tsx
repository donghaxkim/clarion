"use client";

import { useState, useEffect } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, CheckCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { SOCIAL_PROOF } from "@/lib/mock-case";

type State = "idle" | "loading" | "success";

export default function WaitlistCTA() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");
  const [position, setPosition] = useState<number | null>(null);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    // Check if already on waitlist
    const saved = localStorage.getItem("clarion_waitlist_position");
    if (saved) {
      setPosition(parseInt(saved, 10));
      setState("success");
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || state !== "idle") return;

    setState("loading");

    // Simulate API call
    await new Promise((r) => setTimeout(r, 1200));

    // Generate a position slightly above the seed
    const pos = SOCIAL_PROOF.waitlistSeed + Math.floor(Math.random() * 20) + 1;
    localStorage.setItem("clarion_waitlist_position", String(pos));
    setPosition(pos);
    setState("success");
  };

  return (
    <div className="max-w-2xl mx-auto px-4 text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: shouldReduceMotion ? 0 : 0.5 }}
      >
        {state === "success" ? (
          <div className="flex flex-col items-center gap-4 p-8 rounded-2xl bg-surface border border-border shadow-glass">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-emerald-400" aria-hidden="true" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-text-primary mb-1">
                You&apos;re on the list
              </h3>
              {position && (
                <p className="text-text-secondary text-sm">
                  You&apos;re{" "}
                  <span className="text-amber-400 font-semibold">
                    #{position.toLocaleString()}
                  </span>{" "}
                  in line. We&apos;ll reach out when your access is ready.
                </p>
              )}
            </div>
            <p className="text-xs text-text-muted">
              Share Clarion to move up the list ↗
            </p>
            <a
              href={`https://twitter.com/intent/tweet?text=${encodeURIComponent("Just joined the waitlist for Clarion — AI that finds contradictions in legal evidence in seconds. This is going to change litigation. clarion.ai")}`}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                "inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium",
                "bg-[#1D9BF0]/10 border border-[#1D9BF0]/20 text-[#1D9BF0]",
                "hover:bg-[#1D9BF0]/20 active:scale-95 transition-all"
              )}
            >
              Share on X (Twitter)
              <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
          </div>
        ) : (
          <>
            <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-3 tracking-tight">
              Get early access
            </h2>
            <p className="text-text-secondary mb-8 text-base leading-relaxed">
              Clarion is in private beta. Join the waitlist and we&apos;ll reach
              out when your team&apos;s access is ready.
            </p>

            <form
              onSubmit={handleSubmit}
              className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto"
            >
              <label htmlFor="waitlist-email" className="sr-only">
                Email address
              </label>
              <input
                id="waitlist-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@lawfirm.com"
                className={cn(
                  "flex-1 px-4 py-3 rounded-xl text-sm",
                  "bg-surface border border-border text-text-primary placeholder:text-text-muted",
                  "focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/50",
                  "transition-colors min-h-[44px]"
                )}
                aria-label="Email address"
              />
              <button
                type="submit"
                disabled={state === "loading"}
                className={cn(
                  "inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl",
                  "bg-amber-500 text-background font-semibold text-sm",
                  "hover:bg-amber-400 active:scale-95 transition-all duration-150",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "min-h-[44px] whitespace-nowrap"
                )}
                aria-label="Join waitlist"
              >
                {state === "loading" ? (
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                ) : (
                  <>
                    Join Waitlist
                    <ArrowRight className="w-4 h-4" aria-hidden="true" />
                  </>
                )}
              </button>
            </form>

            <p className="mt-4 text-xs text-text-muted">
              No spam. Unsubscribe anytime. Already{" "}
              <span className="text-text-secondary">
                {(SOCIAL_PROOF.waitlistSeed + 12).toLocaleString()} people
              </span>{" "}
              waiting.
            </p>
          </>
        )}
      </motion.div>
    </div>
  );
}
