"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isTyping?: boolean;
}

interface ChatMessageProps {
  message: Message;
  index: number;
}

export function ChatMessage({ message, index }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05 }}
      className={cn("flex", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="w-6 h-6 rounded-sm bg-gold-500/20 border border-gold-500/30 flex items-center justify-center mr-2.5 mt-0.5 flex-shrink-0">
          <span className="text-[9px] font-bold text-gold-400 tracking-tight">AI</span>
        </div>
      )}
      <div
        className={cn(
          "max-w-[80%] px-3.5 py-2.5 rounded text-sm leading-relaxed",
          isUser
            ? "bg-gold-500/10 border border-gold-500/20 text-text-primary"
            : "bg-surface border border-border text-text-secondary"
        )}
      >
        {message.isTyping ? (
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-gold-400/60 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-gold-400/60 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-gold-400/60 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        ) : (
          message.content
        )}
      </div>
    </motion.div>
  );
}
