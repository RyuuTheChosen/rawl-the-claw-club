"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface HealthBarProps {
  health: number; // 0.0 - 1.0
  side: "left" | "right";
  label?: string;
}

export function HealthBar({ health, side, label }: HealthBarProps) {
  const percent = Math.max(0, Math.min(100, health * 100));
  const prevPercent = useRef(percent);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (percent < prevPercent.current - 2) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 200);
      prevPercent.current = percent;
      return () => clearTimeout(t);
    }
    prevPercent.current = percent;
  }, [percent]);

  const barColor =
    percent > 50
      ? "from-green-500 to-green-400"
      : percent > 25
        ? "from-yellow-500 to-yellow-400"
        : "from-red-500 to-red-400";

  return (
    <div className="w-full">
      {label && (
        <div
          className={cn(
            "mb-0.5 font-mono text-[10px] text-muted-foreground",
            side === "right" && "text-right",
          )}
        >
          {label}
        </div>
      )}
      <div
        className={cn(
          "relative h-4 w-full overflow-hidden rounded-sm bg-muted/60",
          flash && "ring-1 ring-white/40",
        )}
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${side === "left" ? "Player 1" : "Player 2"} health: ${Math.round(percent)} percent`}
      >
        {/* Segmented lines */}
        <div className="absolute inset-0 z-10 flex">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="flex-1 border-r border-background/20 last:border-r-0"
            />
          ))}
        </div>
        {/* Health fill */}
        <div
          className={cn(
            "h-full bg-gradient-to-r transition-all duration-200",
            barColor,
            side === "right" && "ml-auto",
          )}
          style={{ width: `${percent}%` }}
        />
        {/* HP number overlay */}
        <div
          className={cn(
            "absolute inset-0 z-20 flex items-center px-1.5 font-mono text-[9px] font-bold text-white drop-shadow-md",
            side === "right" && "justify-end",
          )}
        >
          {Math.round(percent)}%
        </div>
      </div>
    </div>
  );
}
