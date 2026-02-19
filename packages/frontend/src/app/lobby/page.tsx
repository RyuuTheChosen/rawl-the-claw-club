"use client";

import { useCallback, useState } from "react";
import { PaginatedResponse, Match } from "@/types";
import { getMatches } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { MatchCard } from "@/components/MatchCard";
import { MatchCardSkeleton } from "@/components/MatchCardSkeleton";
import { ArcadeButton } from "@/components/ArcadeButton";
import { PageTransition } from "@/components/PageTransition";
import { StaggeredList } from "@/components/StaggeredList";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const FILTERS = ["all", "open", "locked", "resolved", "cancelled"] as const;

export default function LobbyPage() {
  const [filter, setFilter] = useState<string>("open");
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);

  const fetcher = useCallback((): Promise<PaginatedResponse<Match>> => {
    const params: Record<string, string> = {};
    if (filter !== "all") params.status = filter;
    return getMatches(params);
  }, [filter]);

  const mergeMatches = useCallback((incoming: Match[], existing: Match[]): Match[] => {
    const map = new Map(existing.map((m) => [m.id, m]));
    for (const m of incoming) map.set(m.id, m);
    return Array.from(map.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, []);

  const { isPolling } = usePolling({
    fetcher: async () => {
      const data = await fetcher();
      setAllMatches((prev) => mergeMatches(data.items, prev));
      if (!initialLoaded) {
        setNextCursor(data.next_cursor);
        setHasMore(data.has_more);
        setInitialLoaded(true);
      }
      return data;
    },
    interval: 10_000,
    key: filter,
  });

  // Reset on filter change
  const handleFilterChange = (val: string) => {
    setFilter(val);
    setAllMatches([]);
    setNextCursor(null);
    setHasMore(false);
    setInitialLoaded(false);
  };

  const handleLoadMore = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const params: Record<string, string> = { cursor: nextCursor };
      if (filter !== "all") params.status = filter;
      const data = await getMatches(params);
      setAllMatches((prev) => mergeMatches(data.items, prev));
      setNextCursor(data.next_cursor);
      setHasMore(data.has_more);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <h1 className="font-pixel text-base text-neon-orange text-glow-orange sm:text-lg">
              MATCH LOBBY
            </h1>
            {isPolling && (
              <span className="h-2 w-2 animate-pulse rounded-full bg-neon-green" />
            )}
          </div>
          <Tabs value={filter} onValueChange={handleFilterChange}>
            <TabsList>
              {FILTERS.map((f) => (
                <TabsTrigger key={f} value={f} className="font-pixel text-[10px] uppercase">
                  {f}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        {!initialLoaded ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <MatchCardSkeleton key={i} />
            ))}
          </div>
        ) : allMatches.length === 0 ? (
          <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2">
            <span className="font-pixel text-sm text-muted-foreground">
              NO CHALLENGERS FOUND
            </span>
            <span className="text-xs text-muted-foreground/60">
              Check back soon or change filters
            </span>
          </div>
        ) : (
          <>
            <StaggeredList className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {allMatches.map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </StaggeredList>

            {hasMore && (
              <div className="mt-6 flex justify-center">
                <ArcadeButton
                  variant="ghost"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? "LOADING..." : "LOAD MORE"}
                </ArcadeButton>
              </div>
            )}
          </>
        )}
      </div>
    </PageTransition>
  );
}
