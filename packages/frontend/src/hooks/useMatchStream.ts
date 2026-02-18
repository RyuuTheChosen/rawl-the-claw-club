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
  const latestData = useRef<ArrayBuffer | null>(null);
  const rafId = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    if (!matchId || !canvasRef.current) return;

    function renderLatest() {
      rafId.current = 0;
      const data = latestData.current;
      if (!data || !mountedRef.current) return;
      latestData.current = null;
      const blob = new Blob([data], { type: "image/jpeg" });
      createImageBitmap(blob).then((bitmap) => {
        if (!mountedRef.current) {
          bitmap.close();
          return;
        }
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext("2d");
        if (ctx && canvas) {
          ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        }
        bitmap.close();
      });
    }

    const wsUrl = `${WS_BASE}/ws/match/${matchId}/video`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      latestData.current = event.data as ArrayBuffer;
      if (!rafId.current) {
        rafId.current = requestAnimationFrame(renderLatest);
      }
    };

    return () => {
      mountedRef.current = false;
      if (rafId.current) {
        cancelAnimationFrame(rafId.current);
        rafId.current = 0;
      }
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [matchId, canvasRef]);

  return { connected };
}
