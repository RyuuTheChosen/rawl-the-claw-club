"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { Match } from "@/types";
import { StatusBadge } from "./StatusBadge";
import { LivePulse } from "./LivePulse";
import { Countdown } from "./Countdown";
import { cn, getWinnerInfo } from "@/lib/utils";

interface MatchCardProps {
  match: Match;
}

export function MatchCard({ match }: MatchCardProps) {
  const isLive = match.status === "locked";
  const poolTotal = (match.side_a_total + match.side_b_total) / 1e9;
  const winner = getWinnerInfo(match);
  const [countdownDone, setCountdownDone] = useState(false);

  // Reset countdown state when match changes
  useEffect(() => setCountdownDone(false), [match.id]);

  return (
    <Link href={`/arena/${match.id}`}>
      <motion.div
        whileHover={{ scale: 1.02 }}
        className={cn(
          "arcade-border p-4 transition-all",
          isLive && "border-neon-red/30",
        )}
      >
        {/* Top row: game + status */}
        <div className="mb-3 flex items-center justify-between">
          <span className="font-pixel text-[10px] uppercase tracking-wider text-muted-foreground">
            {match.game_id}
          </span>
          <div className="flex items-center gap-2">
            {isLive && <LivePulse />}
            <StatusBadge status={match.status} />
          </div>
        </div>

        {/* VS layout */}
        <div className="mb-3 flex items-center justify-between">
          <span className={cn(
            "font-mono text-sm",
            winner?.side === "a" ? "text-neon-green" : winner?.side === "b" ? "text-neon-cyan/50" : "text-neon-cyan"
          )}>
            {match.fighter_a_name ?? match.fighter_a_id.slice(0, 8)}
          </span>
          <span className="font-pixel text-[10px] text-neon-orange">VS</span>
          <span className={cn(
            "font-mono text-sm",
            winner?.side === "b" ? "text-neon-green" : winner?.side === "a" ? "text-neon-pink/50" : "text-neon-pink"
          )}>
            {match.fighter_b_name ?? match.fighter_b_id.slice(0, 8)}
          </span>
        </div>

        {/* Countdown for open matches — hides when done */}
        {match.status === "open" && match.starts_at && !countdownDone && (
          <div className="mb-2 flex items-center justify-center gap-2 rounded bg-neon-yellow/10 py-1.5">
            <span className="font-pixel text-[9px] text-neon-yellow">STARTS IN</span>
            <Countdown targetDate={match.starts_at} onComplete={() => setCountdownDone(true)} />
          </div>
        )}

        {/* Refund banner for cancelled matches with pools */}
        {match.status === "cancelled" && match.has_pool && (
          <div className="mb-2 rounded bg-neon-yellow/10 py-1.5 text-center">
            <span className="font-pixel text-[9px] text-neon-yellow">REFUND AVAILABLE</span>
          </div>
        )}

        {/* Winner banner for resolved matches */}
        {match.status === "resolved" && winner && (
          <div className="mb-2 rounded bg-neon-green/10 py-1.5 text-center">
            <span className="font-pixel text-[9px] text-neon-green">
              WINNER: {winner.name}
            </span>
          </div>
        )}

        {/* Bottom info */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-pixel text-[10px]">Bo{match.match_format}</span>
          <span className="font-mono text-[10px] text-muted-foreground/60">
            {match.id.slice(0, 8)}
          </span>
          <span className="text-[10px] uppercase">{match.match_type}</span>
          {match.has_pool && poolTotal >= 0.01 && (
            <span className="font-mono text-neon-orange">
              {poolTotal.toFixed(2)} SOL
            </span>
          )}
        </div>
      </motion.div>
    </Link>
  );
}
