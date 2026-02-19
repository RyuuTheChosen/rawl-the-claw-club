"use client";

import { useEffect, useRef } from "react";
import type { MatchDataMessage } from "@/types";
import { useReplayStream } from "@/hooks/useReplayStream";
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
  onReplayData?: (d: MatchDataMessage) => void;
  onReplayEnded?: () => void;
}

export function MatchViewer({
  matchId,
  matchFormat = 3,
  gameId,
  data,
  dataConnected,
  matchStatus,
  replayReady,
  onReplayData,
  onReplayEnded,
}: MatchViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const {
    connected: replayConnected,
    data: replayData,
    ended: replayEnded,
  } = useReplayStream(matchId, replayReady, canvasRef);

  // Lift replay data to parent
  useEffect(() => {
    if (replayData && onReplayData) onReplayData(replayData);
  }, [replayData, onReplayData]);

  useEffect(() => {
    if (replayEnded && onReplayEnded) onReplayEnded();
  }, [replayEnded, onReplayEnded]);

  const videoConnected = replayReady ? replayConnected : false;
  const showComputing = matchStatus === "locked" && !replayReady;

  return (
    <div className="relative">
      <div className="crt-screen relative overflow-hidden rounded-lg border border-border bg-black">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="aspect-[4/3] w-full"
          role="img"
          aria-label="Match replay video stream"
        />

        {/* Computing overlay -- match is locked but replay not ready */}
        {showComputing && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-background/90">
            <ArcadeLoader text="COMPUTING MATCH" />
          </div>
        )}

        {/* Loading overlay -- replay ready but WS not connected yet */}
        {replayReady && !replayConnected && (
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
