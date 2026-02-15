"use client";

import { MatchDataMessage } from "@/types";
import { HealthBar } from "./HealthBar";

interface DataOverlayProps {
  data: MatchDataMessage | null;
}

export function DataOverlay({ data }: DataOverlayProps) {
  if (!data) {
    return (
      <div className="flex items-center justify-center p-8 text-rawl-light/50">
        Waiting for match data...
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between text-sm text-rawl-light/60">
        <span>Round {data.round}</span>
        <span className="font-mono text-lg text-rawl-primary">{data.timer}</span>
        <span>
          {data.round_winner !== null && `Round Winner: P${data.round_winner + 1}`}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 text-xs text-rawl-light/50">Player 1</div>
          <HealthBar
            health={data.health_a / 176}
            side="left"
            label={`${data.health_a}`}
          />
          {data.team_health_a && data.team_health_a.length > 1 && (
            <div className="mt-1 flex gap-1">
              {data.team_health_a.map((h, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded ${
                    i === data.active_char_a ? "bg-rawl-primary" : "bg-rawl-light/20"
                  }`}
                  style={{ opacity: h > 0 ? 1 : 0.3 }}
                />
              ))}
            </div>
          )}
        </div>
        <div>
          <div className="mb-1 text-right text-xs text-rawl-light/50">Player 2</div>
          <HealthBar
            health={data.health_b / 176}
            side="right"
            label={`${data.health_b}`}
          />
          {data.team_health_b && data.team_health_b.length > 1 && (
            <div className="mt-1 flex gap-1">
              {data.team_health_b.map((h, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded ${
                    i === data.active_char_b ? "bg-rawl-secondary" : "bg-rawl-light/20"
                  }`}
                  style={{ opacity: h > 0 ? 1 : 0.3 }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {data.pool_total > 0 && (
        <div className="mt-2 rounded bg-rawl-dark/50 p-2 text-center text-xs">
          <span className="text-rawl-light/50">Pool: </span>
          <span className="font-mono text-rawl-primary">
            {(data.pool_total / 1e9).toFixed(2)} SOL
          </span>
          <span className="ml-4 text-rawl-light/50">Odds: </span>
          <span className="font-mono">
            {data.odds_a.toFixed(2)} / {data.odds_b.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}
