"use client";

import { useEffect, useState } from "react";
import { Match } from "@/types";
import { getMatches } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { PageTransition } from "@/components/PageTransition";
import { StaggeredList } from "@/components/StaggeredList";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const FILTERS = ["all", "open", "locked", "resolved"] as const;

export default function LobbyPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filter !== "all") params.status = filter;
    getMatches(params)
      .then((res) => setMatches(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="font-pixel text-base text-neon-orange text-glow-orange sm:text-lg">
            MATCH LOBBY
          </h1>
          <Tabs value={filter} onValueChange={setFilter}>
            <TabsList>
              {FILTERS.map((f) => (
                <TabsTrigger key={f} value={f} className="font-pixel text-[8px] uppercase">
                  {f}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        {loading ? (
          <ArcadeLoader text="SEARCHING" />
        ) : matches.length === 0 ? (
          <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2">
            <span className="font-pixel text-sm text-muted-foreground">
              NO CHALLENGERS FOUND
            </span>
            <span className="text-xs text-muted-foreground/60">
              Check back soon or change filters
            </span>
          </div>
        ) : (
          <StaggeredList className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {matches.map((match) => (
              <MatchCard key={match.id} match={match} />
            ))}
          </StaggeredList>
        )}
      </div>
    </PageTransition>
  );
}
