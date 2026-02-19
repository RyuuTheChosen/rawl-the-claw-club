"use client";

import { useEffect, useRef, useState } from "react";

interface UseReconnectingWebSocketOptions {
  url: string | null;
  binaryType?: BinaryType;
  onMessage: (event: MessageEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
}

interface UseReconnectingWebSocketReturn {
  connected: boolean;
  wsRef: React.RefObject<WebSocket | null>;
}

export function useReconnectingWebSocket({
  url,
  binaryType = "arraybuffer",
  onMessage,
  onOpen,
  onClose,
  maxRetries = 10,
  baseDelay = 1000,
  maxDelay = 30000,
}: UseReconnectingWebSocketOptions): UseReconnectingWebSocketReturn {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  // Store callbacks in refs to avoid reconnect on callback changes
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    mountedRef.current = true;
    attemptRef.current = 0;

    function cleanup() {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    }

    function connect() {
      if (!url || !mountedRef.current) return;

      const ws = new WebSocket(url);
      ws.binaryType = binaryType;
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        attemptRef.current = 0;
        setConnected(true);
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        onMessageRef.current(event);
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setConnected(false);
        onCloseRef.current?.();

        // Don't reconnect on clean close (code 1000) or if max retries exceeded
        if (event.code === 1000) return;
        if (attemptRef.current >= maxRetries) return;

        const delay = Math.min(baseDelay * Math.pow(2, attemptRef.current), maxDelay);
        attemptRef.current++;
        timeoutRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onclose will fire after onerror, so reconnect logic is there
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      cleanup();
      setConnected(false);
    };
  }, [url, binaryType, maxRetries, baseDelay, maxDelay]);

  return { connected, wsRef };
}
