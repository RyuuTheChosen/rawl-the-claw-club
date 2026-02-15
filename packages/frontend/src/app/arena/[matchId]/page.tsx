"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Match } from "@/types";
import { getMatch } from "@/lib/api";
import { MatchViewer } from "@/components/MatchViewer";
import { BettingPanel } from "@/components/BettingPanel";
import { useMatchDataStream } from "@/hooks/useMatchStream";

export default function ArenaPage() {
  const params = useParams();
  const matchId = params.matchId as string;
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const { data } = useMatchDataStream(matchId);

  useEffect(() => {
    getMatch(matchId)
      .then(setMatch)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-rawl-light/50">Loading match...</div>
      </div>
    );
  }

  if (!match) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-red-400">Match not found</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">
          <span className="text-rawl-light/50">Arena</span>{" "}
          <span className="text-xs text-rawl-light/30">{matchId.slice(0, 8)}</span>
        </h1>
        <span className="text-sm uppercase text-rawl-light/40">{match.game_id}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <MatchViewer matchId={matchId} />
        <div className="space-y-4">
          <BettingPanel matchId={matchId} data={data} />
          <div className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4">
            <h3 className="mb-2 text-sm font-semibold text-rawl-light/80">Match Info</h3>
            <dl className="space-y-1 text-xs">
              <div className="flex justify-between">
                <dt className="text-rawl-light/40">Format</dt>
                <dd>{match.match_format.toUpperCase()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-rawl-light/40">Type</dt>
                <dd>{match.match_type}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-rawl-light/40">Status</dt>
                <dd>{match.status}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
