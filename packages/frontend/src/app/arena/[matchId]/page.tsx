"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Match } from "@/types";
import { getMatch } from "@/lib/api";
import { MatchViewer } from "@/components/MatchViewer";
import { BettingPanel } from "@/components/BettingPanel";
import { useMatchDataStream } from "@/hooks/useMatchStream";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { PageTransition } from "@/components/PageTransition";
import { StatusBadge } from "@/components/StatusBadge";

export default function ArenaPage() {
  const params = useParams();
  const matchId = params.matchId as string;
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const { data, connected: dataConnected } = useMatchDataStream(matchId);

  useEffect(() => {
    getMatch(matchId)
      .then(setMatch)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) {
    return <ArcadeLoader fullPage text="LOADING ARENA" />;
  }

  if (!match) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2">
        <span className="font-pixel text-sm text-neon-red">MATCH NOT FOUND</span>
        <span className="text-xs text-muted-foreground">{matchId}</span>
      </div>
    );
  }

  return (
    <PageTransition>
      <div className="mx-auto max-w-7xl px-4 py-4">
        {/* Header */}
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-pixel text-xs text-neon-orange text-glow-orange sm:text-sm">
              ARENA
            </h1>
            <StatusBadge status={match.status} />
            <span className="font-mono text-[10px] text-muted-foreground">
              {matchId.slice(0, 8)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-pixel text-[8px] uppercase text-muted-foreground">
              {match.game_id}
            </span>
            <span className="font-pixel text-[8px] text-muted-foreground">
              Bo{match.match_format}
            </span>
          </div>
        </div>

        {/* Fighter names */}
        <div className="mb-3 flex items-center justify-between px-1">
          <span className="font-mono text-sm text-neon-cyan">
            {match.fighter_a_id.slice(0, 8)}
          </span>
          <span className="font-pixel text-xs text-neon-orange">VS</span>
          <span className="font-mono text-sm text-neon-pink">
            {match.fighter_b_id.slice(0, 8)}
          </span>
        </div>

        {/* Main layout */}
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <MatchViewer matchId={matchId} matchFormat={match.match_format} gameId={match.game_id} data={data} dataConnected={dataConnected} />
          <div className="space-y-4">
            <BettingPanel matchId={matchId} data={data} matchStatus={match.status} />
            {/* Match Info card */}
            <div className="arcade-border p-4">
              <h3 className="mb-2 font-pixel text-[10px] text-foreground">MATCH INFO</h3>
              <dl className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Format</dt>
                  <dd className="font-mono">Bo{match.match_format}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="uppercase">{match.match_type}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="uppercase">{match.status}</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
