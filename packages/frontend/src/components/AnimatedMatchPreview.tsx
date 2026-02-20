"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { HealthBar } from "@/components/HealthBar";
import { RoundIndicator } from "@/components/RoundIndicator";

// --- Simulation engine (pure logic, no React) ---

interface SimState {
  healthA: number; // 0.0 - 1.0
  healthB: number;
  timer: number; // seconds remaining in round
  winsA: number;
  winsB: number;
  phase: "intro" | "fighting" | "round_end" | "match_end";
  phaseTimer: number; // ticks remaining in current phase
}

function createInitialState(): SimState {
  return {
    healthA: 1.0,
    healthB: 1.0,
    timer: 60,
    winsA: 0,
    winsB: 0,
    phase: "intro",
    phaseTimer: 20, // 2s at 100ms ticks
  };
}

function stepSimulation(state: SimState): SimState {
  const next = { ...state };
  next.phaseTimer--;

  if (next.phase === "intro") {
    if (next.phaseTimer <= 0) {
      next.phase = "fighting";
      next.phaseTimer = 0;
    }
    return next;
  }

  if (next.phase === "round_end") {
    if (next.phaseTimer <= 0) {
      if (next.winsA >= 2 || next.winsB >= 2) {
        next.phase = "match_end";
        next.phaseTimer = 30; // 3s
      } else {
        next.phase = "fighting";
        next.healthA = 1.0;
        next.healthB = 1.0;
        next.timer = 60;
      }
    }
    return next;
  }

  if (next.phase === "match_end") {
    if (next.phaseTimer <= 0) {
      return createInitialState();
    }
    return next;
  }

  // Fighting phase
  if (next.phaseTimer % 10 === 0 && next.phaseTimer !== 0) {
    next.timer = Math.max(0, next.timer - 1);
  }

  const dmgA = 0.02 + Math.random() * 0.04;
  const dmgB = 0.02 + Math.random() * 0.04;
  next.healthA = Math.max(0, next.healthA - dmgA);
  next.healthB = Math.max(0, next.healthB - dmgB);

  let roundWinner: "a" | "b" | null = null;
  if (next.healthA <= 0) roundWinner = "b";
  else if (next.healthB <= 0) roundWinner = "a";
  else if (next.timer <= 0) roundWinner = next.healthA >= next.healthB ? "a" : "b";

  if (roundWinner) {
    if (roundWinner === "a") next.winsA++;
    else next.winsB++;
    next.phase = "round_end";
    next.phaseTimer = 15; // 1.5s
  }

  return next;
}

// --- React component ---

export function AnimatedMatchPreview() {
  const [state, setState] = useState<SimState>(createInitialState);
  const [reducedMotion, setReducedMotion] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;

    intervalRef.current = setInterval(() => {
      setState((prev) => stepSimulation(prev));
    }, 100);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reducedMotion]);

  // Shared container — fixed height so all phases are consistent
  const containerClass =
    "arcade-border crt-screen relative mx-auto mt-8 w-full max-w-xl h-[260px] flex flex-col items-center justify-center bg-background/50 px-8 py-6 overflow-hidden";

  if (reducedMotion) {
    return (
      <div className={containerClass}>
        <HUD healthA={0.6} healthB={0.6} timer={45} winsA={0} winsB={0} />
      </div>
    );
  }

  return (
    <div className={containerClass}>
      {/* HUD is always visible — gives consistent layout */}
      <HUD
        healthA={state.phase === "intro" ? 1.0 : state.healthA}
        healthB={state.phase === "intro" ? 1.0 : state.healthB}
        timer={state.phase === "intro" ? 60 : state.timer}
        winsA={state.winsA}
        winsB={state.winsB}
      />

      {/* Center area — phase-specific content */}
      <div className="flex h-14 items-center justify-center">
        <AnimatePresence mode="wait">
          {state.phase === "intro" && (
            <motion.div
              key="vs"
              initial={{ scale: 3, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}
              className="font-pixel text-2xl text-neon-orange text-glow-orange"
            >
              VS
            </motion.div>
          )}
          {state.phase === "fighting" && (
            <motion.div
              key="fight"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-16"
            >
              <motion.span
                animate={{ x: [0, 4, -4, 0] }}
                transition={{ repeat: Infinity, duration: 0.4 }}
                className="font-pixel text-sm text-neon-cyan text-glow-cyan"
              >
                P1
              </motion.span>
              <motion.span
                animate={{ x: [0, -4, 4, 0] }}
                transition={{ repeat: Infinity, duration: 0.4 }}
                className="font-pixel text-sm text-neon-pink text-glow-pink"
              >
                P2
              </motion.span>
            </motion.div>
          )}
          {state.phase === "round_end" && (
            <motion.div
              key="ko"
              initial={{ scale: 2, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ opacity: 0 }}
              className="font-pixel text-xl text-neon-red text-glow-orange"
            >
              KO
            </motion.div>
          )}
          {state.phase === "match_end" && (
            <motion.div
              key="win"
              initial={{ scale: 2, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ opacity: 0 }}
              className="font-pixel text-lg text-neon-orange text-glow-orange"
            >
              {state.winsA >= 2 ? "P1 WINS" : "P2 WINS"}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/** Always-visible HUD: health bars + timer + round dots */
function HUD({
  healthA,
  healthB,
  timer,
  winsA,
  winsB,
}: {
  healthA: number;
  healthB: number;
  timer: number;
  winsA: number;
  winsB: number;
}) {
  return (
    <div className="flex w-full flex-col items-center gap-3">
      {/* Health bars + timer */}
      <div className="flex w-full items-center gap-3">
        <span className="font-pixel text-xs text-neon-cyan shrink-0">P1</span>
        <div className="flex-1">
          <HealthBar health={healthA} side="left" />
        </div>
        <span className="font-mono text-sm text-muted-foreground tabular-nums w-8 text-center shrink-0">
          {timer}
        </span>
        <div className="flex-1">
          <HealthBar health={healthB} side="right" />
        </div>
        <span className="font-pixel text-xs text-neon-pink shrink-0">P2</span>
      </div>
      {/* Round indicator */}
      <RoundIndicator totalRounds={3} winsNeeded={2} winsA={winsA} winsB={winsB} />
    </div>
  );
}
