import { cn } from "@/lib/utils";
import { forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-gold-500 text-background font-bold hover:bg-gold-400 shadow-glow-gold active:scale-[0.97]",
  secondary:
    "bg-surface border border-border text-text-primary hover:border-gold-500/40 hover:text-gold-400 active:scale-[0.97]",
  ghost:
    "text-text-secondary hover:text-text-primary hover:bg-surface active:scale-[0.97]",
  danger:
    "bg-danger/10 border border-danger/25 text-danger hover:bg-danger/20 active:scale-[0.97]",
};

const sizeClasses: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs rounded gap-1.5",
  md: "px-4 py-2.5 text-sm rounded gap-2",
  lg: "px-6 py-3.5 text-base rounded gap-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "secondary",
      size = "md",
      isLoading,
      children,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-150 min-h-[36px]",
          "disabled:opacity-40 disabled:pointer-events-none",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
