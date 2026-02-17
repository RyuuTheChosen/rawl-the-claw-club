"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface CountdownProps {
  targetDate: string;
  onComplete?: () => void;
  className?: string;
  size?: "sm" | "lg";
}

export function Countdown({ targetDate, onComplete, className, size = "sm" }: CountdownProps) {
  const [secondsLeft, setSecondsLeft] = useState(() => {
    const diff = new Date(targetDate).getTime() - Date.now();
    return Math.max(0, Math.ceil(diff / 1000));
  });

  useEffect(() => {
    if (secondsLeft <= 0) {
      onComplete?.();
      return;
    }

    const timer = setInterval(() => {
      const diff = new Date(targetDate).getTime() - Date.now();
      const next = Math.max(0, Math.ceil(diff / 1000));
      setSecondsLeft(next);
      if (next <= 0) {
        clearInterval(timer);
        onComplete?.();
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [targetDate, secondsLeft, onComplete]);

  if (secondsLeft <= 0) return null;

  const mins = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const display = mins > 0 ? `${mins}:${secs.toString().padStart(2, "0")}` : `${secs}s`;

  return (
    <span
      className={cn(
        "font-mono tabular-nums",
        size === "lg" ? "text-2xl text-neon-yellow text-glow-orange" : "text-xs text-neon-yellow",
        secondsLeft <= 10 && "animate-pulse text-neon-red",
        className,
      )}
    >
      {display}
    </span>
  );
}
