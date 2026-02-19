"use client";

import { useCallback, useRef, useState } from "react";
import type { MatchDataMessage } from "@/types";
import { useReconnectingWebSocket } from "./useReconnectingWebSocket";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api")
  .replace(/\/api\/?$/, "")
  .replace("http", "ws");

export function useReplayStream(
  matchId: string | null,
  replayReady: boolean,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
) {
  const [data, setData] = useState<MatchDataMessage | null>(null);
  const [ended, setEnded] = useState(false);
  const latestFrame = useRef<ArrayBuffer | null>(null);
  const rafId = useRef(0);
  const mountedRef = useRef(true);

  // Suppress reconnection when replay has ended by passing url: null
  const url = matchId && replayReady && !ended ? `${WS_BASE}/ws/replay/${matchId}` : null;

  const onMessage = useCallback(
    (event: MessageEvent) => {
      if (event.data instanceof ArrayBuffer) {
        latestFrame.current = event.data;
        if (!rafId.current) {
          rafId.current = requestAnimationFrame(() => {
            rafId.current = 0;
            const frame = latestFrame.current;
            if (!frame || !mountedRef.current) return;
            latestFrame.current = null;
            const blob = new Blob([frame], { type: "image/jpeg" });
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
          });
        }
      } else {
        try {
          const msg = JSON.parse(event.data);
          if (msg.status === "ended") {
            setEnded(true);
          } else {
            setData(msg as MatchDataMessage);
          }
        } catch {
          // Ignore parse errors
        }
      }
    },
    [canvasRef],
  );

  const { connected } = useReconnectingWebSocket({
    url,
    binaryType: "arraybuffer",
    onMessage,
  });

  return { connected, data, ended };
}
