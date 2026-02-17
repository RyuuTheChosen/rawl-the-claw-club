"use client";

import { useEffect, useRef, useState } from "react";
import type { MatchDataMessage } from "@/types";

// WS base: strip /api suffix since WebSocket routes mount at /ws, not /api/ws
const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api")
  .replace(/\/api\/?$/, "")
  .replace("http", "ws");

export function useMatchDataStream(matchId: string | null) {
  const [data, setData] = useState<MatchDataMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId) return;

    const wsUrl = `${WS_BASE}/ws/match/${matchId}/data`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        setData(JSON.parse(event.data));
      } catch (err) {
        console.error("[WebSocket] Failed to parse data message:", err);
      }
    };

    return () => {
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [matchId]);

  return { data, connected };
}

export function useMatchVideoStream(
  matchId: string | null,
  canvasRef: React.RefObject<HTMLCanvasElement | null>
) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!matchId || !canvasRef.current) return;

    const wsUrl = `${WS_BASE}/ws/match/${matchId}/video`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      const blob = new Blob([event.data], { type: "image/jpeg" });
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        const ctx = canvasRef.current?.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0);
        }
        URL.revokeObjectURL(url);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
      };
      img.src = url;
    };

    return () => {
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [matchId, canvasRef]);

  return { connected };
}
