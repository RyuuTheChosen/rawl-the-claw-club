"use client";

import Link from "next/link";
import { Match } from "@/types";

interface MatchCardProps {
  match: Match;
}

const statusColors: Record<string, string> = {
  open: "bg-blue-500/20 text-blue-400",
  locked: "bg-yellow-500/20 text-yellow-400",
  resolved: "bg-green-500/20 text-green-400",
  cancelled: "bg-red-500/20 text-red-400",
};

export function MatchCard({ match }: MatchCardProps) {
  const isLive = match.status === "locked";
  const poolTotal = (match.side_a_total + match.side_b_total) / 1e9;

  return (
    <Link href={`/arena/${match.id}`}>
      <div className="group rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4 transition hover:border-rawl-primary/30 hover:bg-rawl-dark/70">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-rawl-light/40">
            {match.game_id}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              statusColors[match.status] ?? "bg-rawl-dark/30 text-rawl-light/50"
            }`}
          >
            {isLive && "LIVE - "}
            {match.status.toUpperCase()}
          </span>
        </div>

        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-medium text-rawl-light/80">
            {match.fighter_a_id.slice(0, 8)}
          </div>
          <div className="text-xs text-rawl-light/40">vs</div>
          <div className="text-sm font-medium text-rawl-light/80">
            {match.fighter_b_id.slice(0, 8)}
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-rawl-light/40">
          <span>Bo{match.match_format}</span>
          <span>{match.match_type}</span>
          {match.has_pool && poolTotal > 0 && (
            <span className="font-mono text-rawl-primary">
              {poolTotal.toFixed(2)} SOL
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
