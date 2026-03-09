import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  glow?: "gold" | "danger" | "none";
}

export function Card({ children, className, glow = "none" }: CardProps) {
  return (
    <div
      className={cn(
        "rounded bg-surface border border-border overflow-hidden",
        glow === "gold" && "shadow-glass-gold",
        glow === "danger" && "shadow-[0_0_0_1px_rgba(196,92,92,0.2),0_8px_32px_rgba(0,0,0,0.4)]",
        glow === "none" && "shadow-glass",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "px-4 py-3 border-b border-border flex items-center justify-between",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("p-4", className)}>{children}</div>;
}
