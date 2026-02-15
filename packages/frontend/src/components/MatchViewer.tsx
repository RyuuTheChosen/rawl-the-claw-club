"use client";

import { useRef } from "react";
import { useMatchDataStream, useMatchVideoStream } from "@/hooks/useMatchStream";
import { DataOverlay } from "./DataOverlay";

interface MatchViewerProps {
  matchId: string;
}

export function MatchViewer({ matchId }: MatchViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { data, connected: dataConnected } = useMatchDataStream(matchId);
  const { connected: videoConnected } = useMatchVideoStream(matchId, canvasRef);

  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-lg border border-rawl-dark/30 bg-black">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="aspect-[4/3] w-full"
        />
        {!videoConnected && (
          <div className="absolute inset-0 flex items-center justify-center bg-rawl-dark/80">
            <div className="text-sm text-rawl-light/50">
              {dataConnected ? "Connecting video..." : "Connecting..."}
            </div>
          </div>
        )}
        <div className="absolute right-2 top-2 flex gap-1">
          <div
            className={`h-2 w-2 rounded-full ${videoConnected ? "bg-green-400" : "bg-red-400"}`}
            title={videoConnected ? "Video connected" : "Video disconnected"}
          />
          <div
            className={`h-2 w-2 rounded-full ${dataConnected ? "bg-green-400" : "bg-red-400"}`}
            title={dataConnected ? "Data connected" : "Data disconnected"}
          />
        </div>
      </div>
      <DataOverlay data={data} />
    </div>
  );
}
