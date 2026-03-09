import { cn } from "@/lib/utils";

type Variant = "gold" | "danger" | "warning" | "success" | "info" | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}

const variantClasses: Record<Variant, string> = {
  gold: "bg-gold-500/15 text-gold-400 border border-gold-500/30",
  danger: "bg-danger/10 text-danger border border-danger/25",
  warning: "bg-amber-500/10 text-amber-400 border border-amber-500/25",
  success: "bg-success/10 text-success border border-success/25",
  info: "bg-indigo-500/10 text-indigo-400 border border-indigo-500/25",
  muted: "bg-surface-raised text-text-muted border border-border",
};

export function Badge({ children, variant = "muted", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide uppercase",
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
