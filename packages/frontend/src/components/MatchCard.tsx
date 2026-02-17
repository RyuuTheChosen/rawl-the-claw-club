"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Match } from "@/types";
import { StatusBadge } from "./StatusBadge";
import { LivePulse } from "./LivePulse";
import { cn } from "@/lib/utils";

interface MatchCardProps {
  match: Match;
}

export function MatchCard({ match }: MatchCardProps) {
  const isLive = match.status === "locked";
  const poolTotal = (match.side_a_total + match.side_b_total) / 1e9;

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
          <span className="font-pixel text-[8px] uppercase tracking-wider text-muted-foreground">
            {match.game_id}
          </span>
          <div className="flex items-center gap-2">
            {isLive && <LivePulse />}
            <StatusBadge status={match.status} />
          </div>
        </div>

        {/* VS layout */}
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-sm text-neon-cyan">
            {match.fighter_a_id.slice(0, 8)}
          </span>
          <span className="font-pixel text-[10px] text-neon-orange">VS</span>
          <span className="font-mono text-sm text-neon-pink">
            {match.fighter_b_id.slice(0, 8)}
          </span>
        </div>

        {/* Bottom info */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-pixel text-[8px]">Bo{match.match_format}</span>
          <span className="text-[10px] uppercase">{match.match_type}</span>
          {match.has_pool && poolTotal > 0 && (
            <span className="font-mono text-neon-orange">
              {poolTotal.toFixed(2)} SOL
            </span>
          )}
        </div>
      </motion.div>
    </Link>
  );
}
