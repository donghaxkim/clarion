"use client";

import { useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatMessage, type Message } from "./ChatMessage";

export interface CaseTypeOption {
  label: string;
  description: string;
}

interface ChatInterfaceProps {
  messages: Message[];
  onSend: (text: string) => void;
  isDisabled?: boolean;
  placeholder?: string;
  inputValue: string;
  onInputChange: (val: string) => void;
  /** When set, case-type chips are shown. Only one can be selected at a time. */
  caseTypeOptions?: CaseTypeOption[];
  selectedCaseType?: string | null;
  onSelectCaseType?: (payload: CaseTypeOption) => void;
}

export function ChatInterface({
  messages,
  onSend,
  isDisabled,
  placeholder = "Describe your case...",
  inputValue,
  onInputChange,
  caseTypeOptions,
  selectedCaseType = null,
  onSelectCaseType,
}: ChatInterfaceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isDisabled) {
        onSend(inputValue.trim());
      }
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputValue.trim() && !isDisabled) {
      onSend(inputValue.trim());
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="shrink-0 px-3 py-2 border-b border-border flex items-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full bg-gold-500" />
        <span className="text-[11px] font-semibold text-text-secondary tracking-wider uppercase">
          Case Brief
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-start gap-2 pt-1">
            <p className="font-display text-lg text-text-primary leading-snug">
              Tell me about your case.
            </p>
            <p className="text-text-muted text-xs leading-relaxed max-w-xs">
              Describe the incident and parties, then upload evidence on the right.
            </p>
            {caseTypeOptions && caseTypeOptions.length > 0 && onSelectCaseType ? (
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {caseTypeOptions.map((option) => {
                  const isSelected = selectedCaseType === option.label;
                  return (
                    <button
                      key={option.label}
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onSelectCaseType(option);
                      }}
                      className={cn(
                        "text-left text-[11px] px-2.5 py-1 rounded border transition-colors cursor-pointer",
                        isSelected
                          ? "bg-ink text-background border-ink"
                          : "text-text-muted hover:text-gold-400 border-border hover:border-gold-500/30 bg-surface"
                      )}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={msg.id} message={msg} index={i} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="shrink-0 px-3 py-2 border-t border-border">
        <div className="flex items-center gap-1.5">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isDisabled}
            placeholder={placeholder}
            rows={1}
            className={cn(
              "flex-1 min-w-0 h-8 resize-none rounded px-2.5 py-1.5 box-border text-sm",
              "bg-surface-raised border border-border text-text-primary placeholder:text-text-muted leading-tight",
              "focus:outline-none focus:border-gold-500/50 transition-colors disabled:opacity-40"
            )}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isDisabled}
            className={cn(
              "w-8 h-8 shrink-0 rounded flex items-center justify-center",
              "bg-gold-500 text-background hover:bg-gold-400",
              "disabled:opacity-40 disabled:pointer-events-none transition-all active:scale-95"
            )}
          >
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </form>
    </div>
  );
}
