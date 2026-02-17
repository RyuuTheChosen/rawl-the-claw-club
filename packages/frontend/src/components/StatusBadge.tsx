"use client";

import { cn } from "@/lib/utils";

type Status = string;

const statusConfig: Record<string, { bg: string; text: string; label?: string }> = {
  open: { bg: "bg-neon-blue/20", text: "text-neon-blue" },
  locked: { bg: "bg-neon-yellow/20", text: "text-neon-yellow" },
  resolved: { bg: "bg-neon-green/20", text: "text-neon-green" },
  cancelled: { bg: "bg-neon-red/20", text: "text-neon-red" },
  ready: { bg: "bg-neon-green/20", text: "text-neon-green" },
  calibrating: { bg: "bg-neon-cyan/20", text: "text-neon-cyan" },
  validating: { bg: "bg-neon-yellow/20", text: "text-neon-yellow" },
  rejected: { bg: "bg-neon-red/20", text: "text-neon-red" },
  suspended: { bg: "bg-neon-red/20", text: "text-neon-red" },
};

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] ?? { bg: "bg-muted", text: "text-muted-foreground" };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider font-pixel",
        config.bg,
        config.text,
        className,
      )}
    >
      {config.label ?? status}
    </span>
  );
}
