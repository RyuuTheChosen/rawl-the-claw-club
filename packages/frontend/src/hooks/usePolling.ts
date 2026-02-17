"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UsePollingOptions<T> {
  fetcher: () => Promise<T>;
  interval?: number;
  enabled?: boolean;
  key?: string;
}

interface UsePollingResult<T> {
  data: T | null;
  isPolling: boolean;
  lastUpdated: Date | null;
  error: string | null;
  refresh: () => void;
}

export function usePolling<T>({
  fetcher,
  interval = 10_000,
  enabled = true,
  key = "",
}: UsePollingOptions<T>): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const doFetch = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fetch failed");
    }
  }, []);

  const startPolling = useCallback(() => {
    clearTimer();
    setIsPolling(true);
    intervalRef.current = setInterval(doFetch, interval);
  }, [clearTimer, doFetch, interval]);

  const refresh = useCallback(() => {
    doFetch();
  }, [doFetch]);

  // Reset data when key changes
  useEffect(() => {
    setData(null);
    setLastUpdated(null);
    setError(null);
  }, [key]);

  // Main polling lifecycle
  useEffect(() => {
    if (!enabled) {
      clearTimer();
      setIsPolling(false);
      return;
    }

    doFetch();
    startPolling();

    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearTimer();
        setIsPolling(false);
      } else {
        doFetch();
        startPolling();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearTimer();
      setIsPolling(false);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled, key, interval, doFetch, startPolling, clearTimer]);

  return { data, isPolling, lastUpdated, error, refresh };
}
