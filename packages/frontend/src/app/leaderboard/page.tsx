"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LeaderboardEntry } from "@/types";
import { getLeaderboard } from "@/lib/api";

const GAMES = ["sfiii3n", "kof98", "tektagt"];

const divisionColors: Record<string, string> = {
  Diamond: "text-cyan-400",
  Gold: "text-yellow-400",
  Silver: "text-gray-300",
  Bronze: "text-orange-400",
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
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Leaderboard</h1>
        <div className="flex gap-2">
          {GAMES.map((g) => (
            <button
              key={g}
              onClick={() => setGame(g)}
              className={`rounded-full px-3 py-1 text-xs font-medium uppercase transition ${
                game === g
                  ? "bg-rawl-primary text-rawl-dark"
                  : "bg-rawl-dark/50 text-rawl-light/50 hover:text-rawl-light"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-rawl-light/50">Loading...</div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-rawl-dark/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rawl-dark/30 bg-rawl-dark/50 text-left text-xs text-rawl-light/40">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Fighter</th>
                <th className="px-4 py-3">Division</th>
                <th className="px-4 py-3 text-right">Elo</th>
                <th className="px-4 py-3 text-right">W/L</th>
                <th className="px-4 py-3 text-right">Matches</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.fighter_id}
                  className="border-b border-rawl-dark/20 transition hover:bg-rawl-dark/30"
                >
                  <td className="px-4 py-3 font-mono text-rawl-light/50">
                    {entry.rank}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/fighters/${entry.fighter_id}`}
                      className="font-medium text-rawl-primary hover:underline"
                    >
                      {entry.fighter_name}
                    </Link>
                    <div className="text-xs text-rawl-light/30">
                      {entry.owner_wallet.slice(0, 6)}...{entry.owner_wallet.slice(-4)}
                    </div>
                  </td>
                  <td className={`px-4 py-3 text-xs font-semibold ${divisionColors[entry.division] ?? ""}`}>
                    {entry.division}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {entry.elo_rating.toFixed(0)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-green-400">{entry.wins}</span>
                    <span className="text-rawl-light/30">/</span>
                    <span className="text-red-400">{entry.losses}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-rawl-light/50">
                    {entry.matches_played}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
