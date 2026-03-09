"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, User, FileText, AlertTriangle } from "lucide-react";
import { getEntity } from "@/lib/api";
import type { EntityDetail } from "@/lib/types";
import { MOCK_ENTITY_DETAILS } from "@/lib/mock-data";
import { ContradictionCard } from "@/components/analysis/ContradictionCard";
import { cn } from "@/lib/utils";

interface EntityPanelProps {
  caseId: string;
  entityName: string;
  onClose: () => void;
}

export function EntityPanel({
  caseId,
  entityName,
  onClose,
}: EntityPanelProps) {
  const [data, setData] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getEntity(caseId, entityName)
      .then(setData)
      .catch(() => {
        setData(MOCK_ENTITY_DETAILS[entityName] ?? null);
      })
      .finally(() => setLoading(false));
  }, [caseId, entityName]);

  if (loading && !data) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-40 bg-black/40"
          onClick={onClose}
          aria-hidden
        />
        <motion.aside
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          className="fixed top-0 right-0 bottom-0 w-[400px] z-50 bg-surface border-l border-border flex flex-col shadow-xl"
        >
          <div className="p-5 flex items-center justify-between border-b border-border">
            <div className="h-6 w-32 bg-surface-raised rounded animate-pulse" />
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded hover:bg-surface-raised text-text-muted"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            <div className="h-20 bg-surface-raised rounded animate-pulse" />
            <div className="h-32 bg-surface-raised rounded animate-pulse" />
          </div>
        </motion.aside>
      </AnimatePresence>
    );
  }

  const entity = data ?? {
    name: entityName,
    type: "unknown",
    facts: [],
    contradictions: [],
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <motion.aside
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "tween", duration: 0.25 }}
        className="fixed top-0 right-0 bottom-0 w-[400px] z-50 bg-surface border-l border-border flex flex-col shadow-xl"
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded bg-surface-raised border border-border flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-text-muted" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-text-primary truncate">
                {entity.name}
              </h2>
              <p className="text-[10px] text-text-muted capitalize">
                {entity.type}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded hover:bg-surface-raised text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* All Facts */}
          <section>
            <h3 className="flex items-center gap-2 text-xs font-semibold text-text-primary mb-3">
              <FileText className="w-3.5 h-3.5 text-gold-400" />
              All Facts
            </h3>
            <ul className="space-y-2.5">
              {entity.facts.map((fact, i) => (
                <li
                  key={i}
                  className="rounded bg-surface-raised border border-border p-2.5 space-y-1"
                >
                  <p className="text-[11px] text-text-secondary leading-relaxed">
                    {fact.claim}
                  </p>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-text-muted">
                      {fact.dimension} · {fact.source_filename}
                    </span>
                    <div
                      className={cn(
                        "h-1 w-12 rounded-full overflow-hidden bg-border",
                        fact.reliability >= 0.7 && "bg-success/30",
                        fact.reliability >= 0.4 &&
                          fact.reliability < 0.7 &&
                          "bg-amber-500/30",
                        fact.reliability < 0.4 && "bg-danger/30"
                      )}
                    >
                      <div
                        className="h-full bg-gold-500/80 rounded-full"
                        style={{ width: `${fact.reliability * 100}%` }}
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Contradictions */}
          {entity.contradictions.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-xs font-semibold text-text-primary mb-3">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                Contradictions
              </h3>
              <div className="space-y-3">
                {entity.contradictions.map((c, i) => (
                  <ContradictionCard
                    key={c.id}
                    contradiction={c}
                    index={i}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Deposition Questions */}
          {entity.deposition_questions &&
            entity.deposition_questions.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-text-primary mb-3">
                  Deposition Questions
                </h3>
                <ol className="list-decimal list-inside space-y-2 text-[11px] text-text-secondary leading-relaxed">
                  {entity.deposition_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ol>
              </section>
            )}
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}
