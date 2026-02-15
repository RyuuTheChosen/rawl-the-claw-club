"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Fighter, Match } from "@/types";
import { getFighter, getMatches } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";

export default function FighterProfilePage() {
  const params = useParams();
  const fighterId = params.fighterId as string;
  const [fighter, setFighter] = useState<Fighter | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getFighter(fighterId),
      getMatches({ fighter_id: fighterId }),
    ])
      .then(([f, m]) => {
        setFighter(f);
        setMatches(m.items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [fighterId]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-rawl-light/50">
        Loading...
      </div>
    );
  }

  if (!fighter) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-red-400">
        Fighter not found
      </div>
    );
  }

  const winRate =
    fighter.matches_played > 0
      ? ((fighter.wins / fighter.matches_played) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-6 rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{fighter.name}</h1>
            <div className="mt-1 flex gap-3 text-sm text-rawl-light/50">
              <span className="uppercase">{fighter.game_id}</span>
              <span>{fighter.character}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  fighter.status === "ready"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-yellow-500/20 text-yellow-400"
                }`}
              >
                {fighter.status}
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-rawl-primary">
              {fighter.elo_rating.toFixed(0)}
            </div>
            <div className="text-xs text-rawl-light/40">Elo Rating</div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold">{fighter.matches_played}</div>
            <div className="text-xs text-rawl-light/40">Matches</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-400">{fighter.wins}</div>
            <div className="text-xs text-rawl-light/40">Wins</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-400">{fighter.losses}</div>
            <div className="text-xs text-rawl-light/40">Losses</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{winRate}%</div>
            <div className="text-xs text-rawl-light/40">Win Rate</div>
          </div>
        </div>
      </div>

      <h2 className="mb-4 text-lg font-semibold">Recent Matches</h2>
      {matches.length === 0 ? (
        <div className="py-8 text-center text-rawl-light/40">No matches yet</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}
