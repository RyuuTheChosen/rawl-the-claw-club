"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { LeaderboardEntry } from "@/types";
import { getLeaderboard } from "@/lib/api";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { PageTransition } from "@/components/PageTransition";
import { DivisionBadge } from "@/components/DivisionBadge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const GAMES = ["sfiii3n", "kof98", "tektagt"];

const rankStyle: Record<number, string> = {
  1: "text-neon-yellow text-glow-orange",
  2: "text-gray-300",
  3: "text-orange-400",
};

export default function LeaderboardPage() {
  const [game, setGame] = useState(GAMES[0]);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getLeaderboard(game, 50)
      .then(setEntries)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [game]);

  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="font-pixel text-base text-neon-orange text-glow-orange sm:text-lg">
            HIGH SCORES
          </h1>
          <Tabs value={game} onValueChange={setGame}>
            <TabsList>
              {GAMES.map((g) => (
                <TabsTrigger key={g} value={g} className="font-pixel text-[8px] uppercase">
                  {g}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        {loading ? (
          <ArcadeLoader text="LOADING SCORES" />
        ) : entries.length === 0 ? (
          <div className="flex min-h-[40vh] items-center justify-center">
            <span className="font-pixel text-sm text-muted-foreground">NO FIGHTERS RANKED</span>
          </div>
        ) : (
          <div className="arcade-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left">
                  <th className="px-4 py-3 font-pixel text-[8px] text-muted-foreground">#</th>
                  <th className="px-4 py-3 font-pixel text-[8px] text-muted-foreground">FIGHTER</th>
                  <th className="px-4 py-3 font-pixel text-[8px] text-muted-foreground">DIV</th>
                  <th className="px-4 py-3 text-right font-pixel text-[8px] text-muted-foreground">ELO</th>
                  <th className="hidden px-4 py-3 text-right font-pixel text-[8px] text-muted-foreground sm:table-cell">W/L</th>
                  <th className="hidden px-4 py-3 text-right font-pixel text-[8px] text-muted-foreground sm:table-cell">MATCHES</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, i) => (
                  <motion.tr
                    key={entry.fighter_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i * 0.03, 0.36) }}
                    className="border-b border-border/50 transition-colors hover:bg-muted/20"
                  >
                    <td className={cn("px-4 py-3 font-mono", rankStyle[entry.rank] ?? "text-muted-foreground")}>
                      {entry.rank}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/fighters/${entry.fighter_id}`}
                        className="font-medium text-neon-orange hover:text-glow-orange hover:underline"
                      >
                        {entry.fighter_name}
                      </Link>
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {entry.owner_wallet.slice(0, 6)}...{entry.owner_wallet.slice(-4)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <DivisionBadge division={entry.division} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-neon-orange">
                      {entry.elo_rating.toFixed(0)}
                    </td>
                    <td className="hidden px-4 py-3 text-right sm:table-cell">
                      <span className="text-neon-green">{entry.wins}</span>
                      <span className="text-muted-foreground">/</span>
                      <span className="text-neon-red">{entry.losses}</span>
                    </td>
                    <td className="hidden px-4 py-3 text-right text-muted-foreground sm:table-cell">
                      {entry.matches_played}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageTransition>
  );
}
