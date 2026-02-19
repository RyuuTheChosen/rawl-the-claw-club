"use client";

import { cn } from "@/lib/utils";

interface RoundIndicatorProps {
  totalRounds: number;
  winsNeeded: number;
  winsA: number;
  winsB: number;
  className?: string;
}

export function RoundIndicator({
  totalRounds,
  winsNeeded,
  winsA,
  winsB,
  className,
}: RoundIndicatorProps) {
  return (
    <div
      role="status"
      aria-label={`Round ${Math.min(winsA + winsB + 1, totalRounds)}: Player 1 has ${winsA} wins, Player 2 has ${winsB} wins`}
      className={cn("flex items-center gap-4", className)}
    >
      {/* P1 round dots */}
      <div className="flex gap-1">
        {Array.from({ length: winsNeeded }).map((_, i) => (
          <div
            key={`a-${i}`}
            className={cn(
              "h-2.5 w-2.5 rounded-full border",
              i < winsA
                ? "border-neon-cyan bg-neon-cyan shadow-neon-cyan"
                : "border-neon-cyan/30 bg-transparent",
            )}
          />
        ))}
      </div>

      <span className="font-pixel text-[10px] text-muted-foreground">
        RD {Math.min(winsA + winsB + 1, totalRounds)}
      </span>

      {/* P2 round dots */}
      <div className="flex gap-1">
        {Array.from({ length: winsNeeded }).map((_, i) => (
          <div
            key={`b-${i}`}
            className={cn(
              "h-2.5 w-2.5 rounded-full border",
              i < winsB
                ? "border-neon-pink bg-neon-pink shadow-neon-pink"
                : "border-neon-pink/30 bg-transparent",
            )}
          />
        ))}
      </div>
    </div>
  );
}
