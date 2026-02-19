"use client";

import { useEffect, useRef } from "react";
import type { MatchDataMessage } from "@/types";
import { useReplayStream } from "@/hooks/useReplayStream";
import { useLiveStream } from "@/hooks/useLiveStream";
import { DataOverlay } from "./DataOverlay";
import { ArcadeLoader } from "./ArcadeLoader";
import { cn } from "@/lib/utils";

interface MatchViewerProps {
  matchId: string;
  matchFormat?: number;
  gameId?: string;
  data: MatchDataMessage | null;
  dataConnected: boolean;
  matchStatus: string;
  replayReady: boolean;
  isLive: boolean;
  onReplayData?: (d: MatchDataMessage) => void;
  onReplayEnded?: () => void;
  onLiveData?: (d: MatchDataMessage) => void;
  onLiveEnded?: () => void;
}

export function MatchViewer({
  matchId,
  matchFormat = 3,
  gameId,
  data,
  dataConnected,
  matchStatus,
  replayReady,
  isLive,
  onReplayData,
  onReplayEnded,
  onLiveData,
  onLiveEnded,
}: MatchViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Live stream hook (active only when isLive)
  const {
    connected: liveConnected,
    data: liveData,
    ended: liveEnded,
    webCodecsSupported,
  } = useLiveStream(matchId, isLive, canvasRef);

  // Replay stream hook (active only when replay is ready and not live)
  const {
    connected: replayConnected,
    data: replayData,
    ended: replayEnded,
  } = useReplayStream(matchId, replayReady && !isLive, canvasRef);

  // Lift live data to parent
  useEffect(() => {
    if (liveData && onLiveData) onLiveData(liveData);
  }, [liveData, onLiveData]);

  useEffect(() => {
    if (liveEnded && onLiveEnded) onLiveEnded();
  }, [liveEnded, onLiveEnded]);

  // Lift replay data to parent
  useEffect(() => {
    if (replayData && onReplayData) onReplayData(replayData);
  }, [replayData, onReplayData]);

  useEffect(() => {
    if (replayEnded && onReplayEnded) onReplayEnded();
  }, [replayEnded, onReplayEnded]);

  const videoConnected = isLive ? liveConnected : replayReady ? replayConnected : false;

  // Show computing overlay when locked, not live (or no WebCodecs), and no replay
  const showComputing =
    matchStatus === "locked" && !replayReady && (!isLive || !webCodecsSupported);

  return (
    <div className="relative">
      <div className="crt-screen relative overflow-hidden rounded-lg border border-border bg-black">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="aspect-[4/3] w-full"
          role="img"
          aria-label="Match video stream"
        />

        {/* LIVE badge */}
        {isLive && liveConnected && (
          <div className="absolute left-2 top-2 z-50 flex items-center gap-1 rounded bg-neon-red/90 px-2 py-0.5">
            <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
            <span className="font-pixel text-[10px] text-white">LIVE</span>
          </div>
        )}

        {/* Computing overlay -- match is locked but no live stream and no replay */}
        {showComputing && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-background/90">
            <ArcadeLoader text="COMPUTING MATCH" />
          </div>
        )}

        {/* Loading overlay -- replay ready but WS not connected yet */}
        {replayReady && !isLive && !replayConnected && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-background/90">
            <ArcadeLoader text="LOADING REPLAY" />
          </div>
        )}

        {/* Data overlay on top of canvas */}
        <DataOverlay data={data} matchFormat={matchFormat} gameId={gameId} />

        {/* Connection status dots */}
        <div className="absolute right-2 top-2 z-50 flex gap-1">
          <div
            className={cn(
              "h-2 w-2 rounded-full",
              videoConnected ? "bg-neon-green shadow-neon-green" : "bg-neon-red",
            )}
            title={videoConnected ? "Video connected" : "Video disconnected"}
          />
          <div
            className={cn(
              "h-2 w-2 rounded-full",
              dataConnected ? "bg-neon-green shadow-neon-green" : "bg-neon-red",
            )}
            title={dataConnected ? "Data connected" : "Data disconnected"}
          />
        </div>
      </div>
    </div>
  );
}
