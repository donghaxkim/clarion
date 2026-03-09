"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Send, Loader2 } from "lucide-react";
import { editSection } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface SideEditorProps {
  caseId: string;
  sectionId: string;
  onClose: () => void;
  onSaved?: () => void;
  initialContent?: string;
}

export function SideEditor({
  caseId,
  sectionId,
  onClose,
  onSaved,
  initialContent = "",
}: SideEditorProps) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!instruction.trim() || loading) return;
      setLoading(true);
      setError(null);
      try {
        await editSection(caseId, sectionId, instruction.trim());
        onSaved?.();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update section");
      } finally {
        setLoading(false);
      }
    },
    [caseId, sectionId, instruction, loading, onSaved]
  );

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
        className="fixed top-0 right-0 bottom-0 w-full max-w-md z-50 bg-surface border-l border-border flex flex-col shadow-xl"
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">
            Edit section
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded hover:bg-surface-raised text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <div>
            <p className="text-[10px] font-semibold text-text-muted uppercase mb-2">
              Current content
            </p>
            <div className="rounded bg-surface-raised border border-border p-3 text-xs text-text-secondary leading-relaxed max-h-40 overflow-y-auto">
              {initialContent || "Loading..."}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <label className="block">
              <p className="text-[10px] font-semibold text-text-muted uppercase mb-2">
                How would you like to change this section?
              </p>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="e.g. Make the speed estimate more conservative"
                rows={3}
                disabled={loading}
                className={cn(
                  "w-full rounded border border-border bg-surface-raised px-3 py-2.5",
                  "text-sm text-text-primary placeholder:text-text-muted",
                  "focus:outline-none focus:border-gold-500/50",
                  "disabled:opacity-50"
                )}
              />
            </label>
            {error && (
              <p className="text-xs text-danger">{error}</p>
            )}
            <div className="flex gap-2">
              <Button
                type="button"
                variant="ghost"
                size="md"
                onClick={onClose}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={!instruction.trim() || loading}
                className="gap-2"
              >
                {loading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                Apply
              </Button>
            </div>
          </form>
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}
