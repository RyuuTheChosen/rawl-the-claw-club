"use client";

import { useEffect, useState } from "react";
import { Match } from "@/types";
import { getMatches } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";

export default function LobbyPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filter !== "all") params.status = filter;
    getMatches(params)
      .then((res) => setMatches(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  const filters = ["all", "open", "locked", "resolved"];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Match Lobby</h1>
        <div className="flex gap-2">
          {filters.map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setLoading(true);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                filter === f
                  ? "bg-rawl-primary text-rawl-dark"
                  : "bg-rawl-dark/50 text-rawl-light/50 hover:text-rawl-light"
              }`}
            >
              {f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-rawl-light/50">Loading matches...</div>
      ) : matches.length === 0 ? (
        <div className="py-12 text-center text-rawl-light/40">No matches found</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}
