"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MatchDataMessage } from "@/types";
import { useReconnectingWebSocket } from "./useReconnectingWebSocket";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api")
  .replace(/\/api\/?$/, "")
  .replace("http", "ws");

// Binary protocol constants (must match backend broadcaster.py)
const TYPE_SEQ_HEADER = 0x01;
const TYPE_KEYFRAME = 0x02;
const TYPE_DELTA = 0x03;
const TYPE_EOS = 0x04;
const HEADER_SIZE = 13;

export function useLiveStream(
  matchId: string | null,
  isLive: boolean,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
): {
  connected: boolean;
  data: MatchDataMessage | null;
  ended: boolean;
  webCodecsSupported: boolean;
} {
  const [data, setData] = useState<MatchDataMessage | null>(null);
  const [ended, setEnded] = useState(false);
  const mountedRef = useRef(true);
  const decoderRef = useRef<VideoDecoder | null>(null);
  // Buffer SPS+PPS NAL data to prepend to next keyframe (Annex B spec requirement)
  const spsPpsRef = useRef<Uint8Array | null>(null);

  const webCodecsSupported = typeof window !== "undefined" && "VideoDecoder" in window;

  // Set up / tear down VideoDecoder when isLive changes
  useEffect(() => {
    mountedRef.current = true;

    if (!isLive || !webCodecsSupported) {
      return;
    }

    const decoder = new VideoDecoder({
      output: (frame: VideoFrame) => {
        if (!mountedRef.current) {
          frame.close();
          return;
        }
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext("2d");
        if (ctx && canvas) {
          ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
        }
        frame.close();
      },
      error: (e: DOMException) => {
        console.error("VideoDecoder error:", e);
        // Next keyframe (every 0.5s) will recover
      },
    });

    // W3C AVC codec registration: use avc1 + avc.format="annexb" for Annex B NALs.
    // Omit description to signal Annex B format (SPS/PPS inline in bitstream).
    // See: https://www.w3.org/TR/webcodecs-avc-codec-registration/
    decoder.configure({
      codec: "avc1.42001f", // Baseline profile, level 3.1
      optimizeForLatency: true,
      avc: { format: "annexb" },
    } as VideoDecoderConfig);

    decoderRef.current = decoder;

    return () => {
      mountedRef.current = false;
      if (decoder.state !== "closed") {
        decoder.close();
      }
      decoderRef.current = null;
      spsPpsRef.current = null;
    };
  }, [isLive, webCodecsSupported, canvasRef]);

  // Video WS message handler
  const onVideoMessage = useCallback(
    (event: MessageEvent) => {
      if (!(event.data instanceof ArrayBuffer)) return;
      const buf = event.data;
      if (buf.byteLength < HEADER_SIZE) return;

      const view = new DataView(buf);
      const type = view.getUint8(0);
      const timestampUs = Number(view.getBigUint64(1)); // microseconds since match start
      // const seq = view.getUint32(9);

      if (type === TYPE_EOS) {
        setEnded(true);
        return;
      }

      const decoder = decoderRef.current;
      if (!decoder || decoder.state === "closed") return;

      const nalData = new Uint8Array(buf, HEADER_SIZE);

      // Buffer SPS+PPS sequence header — don't feed to decoder standalone.
      // Per W3C spec, Annex B key chunks must contain "both a primary coded picture
      // (IDR) and all parameter sets necessary to decode" in a single chunk.
      if (type === TYPE_SEQ_HEADER) {
        spsPpsRef.current = new Uint8Array(nalData);
        return;
      }

      try {
        let chunkData: Uint8Array;

        if (type === TYPE_KEYFRAME && spsPpsRef.current) {
          // Prepend SPS+PPS to keyframe IDR to form a complete Annex B access unit
          const combined = new Uint8Array(spsPpsRef.current.length + nalData.length);
          combined.set(spsPpsRef.current, 0);
          combined.set(nalData, spsPpsRef.current.length);
          chunkData = combined;
        } else {
          chunkData = nalData;
        }

        const chunkType: EncodedVideoChunkType =
          type === TYPE_KEYFRAME ? "key" : "delta";

        const chunk = new EncodedVideoChunk({
          type: chunkType,
          timestamp: timestampUs,
          data: chunkData,
        });
        decoder.decode(chunk);
      } catch {
        // Decode errors recover on next keyframe
      }
    },
    [],
  );

  // Data WS message handler
  const onDataMessage = useCallback(
    (event: MessageEvent) => {
      if (event.data instanceof ArrayBuffer) return;
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
    },
    [],
  );

  // WebSocket URLs — null when not live or ended
  const videoUrl =
    matchId && isLive && !ended && webCodecsSupported
      ? `${WS_BASE}/ws/match/${matchId}/video`
      : null;
  const dataUrl =
    matchId && isLive && !ended
      ? `${WS_BASE}/ws/match/${matchId}/data`
      : null;

  const { connected: videoConnected } = useReconnectingWebSocket({
    url: videoUrl,
    binaryType: "arraybuffer",
    onMessage: onVideoMessage,
  });

  const { connected: dataConnected } = useReconnectingWebSocket({
    url: dataUrl,
    onMessage: onDataMessage,
  });

  return {
    connected: videoConnected || dataConnected,
    data,
    ended,
    webCodecsSupported,
  };
}
