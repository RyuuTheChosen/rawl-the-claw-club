"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Trophy } from "lucide-react";
import { Match, MatchDataMessage } from "@/types";
import { getMatch } from "@/lib/api";
import { cn, getWinnerInfo } from "@/lib/utils";
import { MatchViewer } from "@/components/MatchViewer";
import { BettingPanel } from "@/components/BettingPanel";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { PageTransition } from "@/components/PageTransition";
import { StatusBadge } from "@/components/StatusBadge";
import { Countdown } from "@/components/Countdown";

export default function ArenaPage() {
  const params = useParams();
  const matchId = params.matchId as string;
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const [replayData, setReplayData] = useState<MatchDataMessage | null>(null);
  const [liveData, setLiveData] = useState<MatchDataMessage | null>(null);
  const [liveEnded, setLiveEnded] = useState(false);

  // Initial fetch
  useEffect(() => {
    getMatch(matchId)
      .then(setMatch)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [matchId]);

  // Derive live/replay state
  const replayReady = !!match?.replay_s3_key;
  const isLive = match?.status === "locked" && !replayReady;

  // Adaptive polling: faster when waiting for replay after live ends, normal otherwise
  const pollInterval = liveEnded && !replayReady ? 2_000 : match?.status === "locked" ? 5_000 : 3_000;

  useEffect(() => {
    if (loading) return;
    const timer = setInterval(() => {
      getMatch(matchId).then(setMatch).catch(() => {});
    }, pollInterval);
    return () => clearInterval(timer);
  }, [matchId, loading, pollInterval]);

  // Effective data: live data takes priority when live, then replay data
  const effectiveData = isLive ? liveData : replayReady ? replayData : null;

  // Derive effective status
  const effectiveStatus: string = replayData?.match_winner
    ? "resolved"
    : liveData?.match_winner
      ? "resolved"
      : match?.status ?? "open";

  const handleReplayData = useCallback((d: MatchDataMessage) => {
    setReplayData(d);
  }, []);

  const handleLiveData = useCallback((d: MatchDataMessage) => {
    setLiveData(d);
  }, []);

  const handleLiveEnded = useCallback(() => {
    setLiveEnded(true);
  }, []);

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

  const nameA = match.fighter_a_name ?? match.fighter_a_id.slice(0, 8);
  const nameB = match.fighter_b_name ?? match.fighter_b_id.slice(0, 8);
  const winner = getWinnerInfo(match, effectiveData);

  return (
    <PageTransition>
      <div className="mx-auto max-w-7xl px-4 py-4">
        {/* Header */}
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-pixel text-xs text-neon-orange text-glow-orange sm:text-sm">
              ARENA
            </h1>
            <StatusBadge status={effectiveStatus} />
            <span className="font-mono text-[10px] text-muted-foreground">
              {matchId.slice(0, 8)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-pixel text-[10px] uppercase text-muted-foreground">
              {match.game_id}
            </span>
            <span className="font-pixel text-[10px] text-muted-foreground">
              Bo{match.match_format}
            </span>
          </div>
        </div>

        {/* Fighter names */}
        <div className="mb-3 flex items-center justify-between px-1">
          <span className={cn("font-mono text-sm", winner?.side === "a" ? "text-neon-green" : "text-neon-cyan")}>
            {nameA}
          </span>
          <span className="font-pixel text-xs text-neon-orange">VS</span>
          <span className={cn("font-mono text-sm", winner?.side === "b" ? "text-neon-green" : "text-neon-pink")}>
            {nameB}
          </span>
        </div>

        {/* Winner banner */}
        {effectiveStatus === "resolved" && winner && (
          <div className="mb-4 flex items-center justify-center gap-2 rounded-lg border border-neon-green/30 bg-neon-green/10 py-3">
            <Trophy className="h-4 w-4 text-neon-green" />
            <span className="font-pixel text-xs text-neon-green text-glow-green">
              WINNER: {winner.name}
            </span>
          </div>
        )}

        {/* Pre-match countdown */}
        {effectiveStatus === "open" && match.starts_at && (
          <div className="mb-4 flex items-center justify-center gap-3 rounded-lg border border-neon-yellow/20 bg-neon-yellow/5 py-3">
            <span className="font-pixel text-xs text-neon-yellow">FIGHT BEGINS IN</span>
            <Countdown targetDate={match.starts_at} size="lg" />
          </div>
        )}

        {/* Main layout */}
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <MatchViewer
            matchId={matchId}
            matchFormat={match.match_format}
            gameId={match.game_id}
            data={effectiveData}
            dataConnected={isLive ? !!liveData : replayReady}
            matchStatus={effectiveStatus}
            replayReady={replayReady}
            isLive={isLive}
            onReplayData={handleReplayData}
            onLiveData={handleLiveData}
            onLiveEnded={handleLiveEnded}
          />
          <div className="space-y-4">
            <BettingPanel
              matchId={matchId}
              data={effectiveData}
              matchStatus={effectiveStatus}
              startsAt={match.starts_at}
              winningSide={winner?.side ?? null}
            />
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
                  <dd className="uppercase">{effectiveStatus}</dd>
                </div>
                {winner && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Winner</dt>
                    <dd className={cn("font-mono", winner.side === "a" ? "text-neon-cyan" : "text-neon-pink")}>
                      {winner.name}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
