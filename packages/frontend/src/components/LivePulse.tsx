"use client";

import { cn } from "@/lib/utils";

interface LivePulseProps {
  className?: string;
}

export function LivePulse({ className }: LivePulseProps) {
  return (
    <span role="status" aria-label="Match is live" className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-live-pulse rounded-full bg-neon-red opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-neon-red" />
      </span>
      <span className="text-[10px] font-pixel uppercase text-neon-red">
        Live
      </span>
    </span>
  );
}
