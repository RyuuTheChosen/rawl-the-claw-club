"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { HealthBar } from "@/components/HealthBar";
import { RoundIndicator } from "@/components/RoundIndicator";
import { VsScreen } from "@/components/VsScreen";

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
      // Check for match end
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
  // Decrement timer every 10 ticks (1s)
  if (next.phaseTimer % 10 === 0 && next.phaseTimer !== 0) {
    next.timer = Math.max(0, next.timer - 1);
  }

  // Random damage each tick
  const dmgA = 0.02 + Math.random() * 0.04;
  const dmgB = 0.02 + Math.random() * 0.04;
  next.healthA = Math.max(0, next.healthA - dmgA);
  next.healthB = Math.max(0, next.healthB - dmgB);

  // Check round end
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

  if (reducedMotion) {
    return (
      <div className="arcade-border crt-screen relative mx-auto mt-6 max-w-lg aspect-[4/3] flex flex-col items-center justify-center gap-3 bg-background/50 p-4">
        <div className="w-full max-w-xs">
          <HealthBar health={0.6} side="left" label="P1" />
        </div>
        <RoundIndicator totalRounds={3} winsNeeded={2} winsA={0} winsB={0} />
        <div className="w-full max-w-xs">
          <HealthBar health={0.6} side="right" label="P2" />
        </div>
        <span className="font-mono text-xs text-muted-foreground">45</span>
      </div>
    );
  }

  return (
    <div className="arcade-border crt-screen relative mx-auto mt-6 max-w-lg aspect-[4/3] flex flex-col items-center justify-center bg-background/50 p-4 overflow-hidden">
      {state.phase === "intro" && (
        <VsScreen fighterA="PLAYER 1" fighterB="PLAYER 2" />
      )}

      {state.phase !== "intro" && (
        <div className="flex w-full flex-col items-center gap-3">
          {/* Health bars */}
          <div className="flex w-full items-center gap-3">
            <div className="flex-1">
              <HealthBar health={state.healthA} side="left" label="P1" />
            </div>
            <span className="font-mono text-xs text-muted-foreground tabular-nums">
              {state.timer}
            </span>
            <div className="flex-1">
              <HealthBar health={state.healthB} side="right" label="P2" />
            </div>
          </div>

          {/* Round indicator */}
          <RoundIndicator
            totalRounds={3}
            winsNeeded={2}
            winsA={state.winsA}
            winsB={state.winsB}
          />

          {/* Match end overlay */}
          {state.phase === "match_end" && (
            <motion.div
              initial={{ scale: 2, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="font-pixel text-xl text-neon-orange text-glow-orange"
            >
              {state.winsA >= 2 ? "P1 WINS" : "P2 WINS"}
            </motion.div>
          )}

          {/* Fighting area placeholder */}
          {state.phase === "fighting" && (
            <div className="flex items-center justify-center gap-12 py-4">
              <motion.div
                animate={{ x: [0, 4, -4, 0] }}
                transition={{ repeat: Infinity, duration: 0.5 }}
                className="font-pixel text-sm text-neon-cyan text-glow-cyan"
              >
                P1
              </motion.div>
              <motion.div
                animate={{ x: [0, -4, 4, 0] }}
                transition={{ repeat: Infinity, duration: 0.5 }}
                className="font-pixel text-sm text-neon-pink text-glow-pink"
              >
                P2
              </motion.div>
            </div>
          )}

          {/* Round end */}
          {state.phase === "round_end" && (
            <motion.div
              initial={{ scale: 1.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="font-pixel text-base text-neon-orange"
            >
              KO
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}
