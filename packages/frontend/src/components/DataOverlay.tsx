"use client";

import { useEffect, useRef, useState } from "react";
import { MatchDataMessage } from "@/types";
import { HealthBar } from "./HealthBar";
import { RoundIndicator } from "./RoundIndicator";

const MAX_HEALTH_MAP: Record<string, number> = {
  sf2ce: 176,
  sfiii3n: 160,
  kof98: 103,
  tektagt: 170,
};
const DEFAULT_MAX_HEALTH = 176;

interface DataOverlayProps {
  data: MatchDataMessage | null;
  matchFormat?: number;
  gameId?: string;
}

export function DataOverlay({ data, matchFormat = 3, gameId }: DataOverlayProps) {
  const maxHealth = gameId ? (MAX_HEALTH_MAP[gameId] ?? DEFAULT_MAX_HEALTH) : DEFAULT_MAX_HEALTH;
  const winsNeeded = Math.ceil(matchFormat / 2);

  const prevRoundWinner = useRef<number | null>(null);
  const [winsA, setWinsA] = useState(0);
  const [winsB, setWinsB] = useState(0);

  useEffect(() => {
    if (data?.round_winner && data.round_winner !== prevRoundWinner.current) {
      if (data.round_winner === 1) setWinsA((w) => w + 1);
      if (data.round_winner === 2) setWinsB((w) => w + 1);
    }
    prevRoundWinner.current = data?.round_winner ?? null;
  }, [data?.round_winner]);

  if (!data) {
    return (
      <div className="absolute inset-0 z-30 flex items-center justify-center bg-background/80">
        <span className="font-pixel text-[10px] text-muted-foreground animate-pulse-glow">
          WAITING FOR MATCH DATA
        </span>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 z-30 pointer-events-none flex flex-col justify-between p-2 sm:p-3">
      {/* Top: Health bars + Timer */}
      <div>
        <div className="flex items-start gap-2">
          {/* P1 health */}
          <div className="flex-1">
            <div className="mb-0.5 font-pixel text-[8px] text-neon-cyan">P1</div>
            <HealthBar health={data.health_a / maxHealth} side="left" label={`${data.health_a}`} />
            {data.team_health_a && data.team_health_a.length > 1 && (
              <div className="mt-0.5 flex gap-0.5">
                {data.team_health_a.map((h, i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-sm ${
                      i === data.active_char_a ? "bg-neon-cyan" : "bg-muted-foreground/30"
                    }`}
                    style={{ opacity: h > 0 ? 1 : 0.3 }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Timer */}
          <div className="flex flex-col items-center px-2">
            <span className="font-pixel text-sm text-neon-yellow text-glow-orange sm:text-lg">
              {data.timer}
            </span>
            <RoundIndicator
              totalRounds={matchFormat}
              winsNeeded={winsNeeded}
              winsA={winsA}
              winsB={winsB}
              className="mt-0.5"
            />
          </div>

          {/* P2 health */}
          <div className="flex-1">
            <div className="mb-0.5 text-right font-pixel text-[8px] text-neon-pink">P2</div>
            <HealthBar health={data.health_b / maxHealth} side="right" label={`${data.health_b}`} />
            {data.team_health_b && data.team_health_b.length > 1 && (
              <div className="mt-0.5 flex gap-0.5">
                {data.team_health_b.map((h, i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-sm ${
                      i === data.active_char_b ? "bg-neon-pink" : "bg-muted-foreground/30"
                    }`}
                    style={{ opacity: h > 0 ? 1 : 0.3 }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: Pool + Odds */}
      {data.pool_total > 0 && (
        <div className="flex items-center justify-center gap-4 rounded bg-background/60 px-3 py-1 backdrop-blur-sm">
          <span className="font-pixel text-[8px] text-muted-foreground">POOL</span>
          <span className="font-mono text-xs text-neon-orange">
            {(data.pool_total / 1e9).toFixed(2)} SOL
          </span>
          <span className="font-pixel text-[8px] text-muted-foreground">ODDS</span>
          <span className="font-mono text-xs">
            <span className="text-neon-cyan">{data.odds_a.toFixed(2)}</span>
            <span className="text-muted-foreground"> / </span>
            <span className="text-neon-pink">{data.odds_b.toFixed(2)}</span>
          </span>
        </div>
      )}
    </div>
  );
}
