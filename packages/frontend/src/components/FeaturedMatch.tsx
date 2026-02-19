"use client";

import Link from "next/link";
import { getMatches } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeButton } from "@/components/ArcadeButton";
import { LivePulse } from "@/components/LivePulse";

const fetchLiveMatch = () => getMatches({ status: "live", limit: 1 });

export function FeaturedMatch() {
  const { data } = usePolling({ fetcher: fetchLiveMatch, interval: 10_000 });

  // Loading state
  if (data === null) {
    return (
      <section className="mx-auto w-full max-w-md px-4 py-8">
        <div className="arcade-border p-6 animate-pulse">
          <div className="h-4 w-24 rounded bg-muted mx-auto" />
          <div className="mt-3 h-6 w-40 rounded bg-muted mx-auto" />
          <div className="mt-4 h-10 w-32 rounded bg-muted mx-auto" />
        </div>
      </section>
    );
  }

  const match = data.items[0];

  if (!match) {
    return (
      <section className="mx-auto w-full max-w-md px-4 py-8">
        <ArcadeCard glowColor="orange" hover={false} className="text-center">
          <p className="font-pixel text-[10px] text-muted-foreground">No live matches</p>
          <Link href="/lobby" className="mt-3 inline-block">
            <ArcadeButton variant="ghost" size="sm">Browse Lobby</ArcadeButton>
          </Link>
        </ArcadeCard>
      </section>
    );
  }

  return (
    <section className="mx-auto w-full max-w-md px-4 py-8">
      <ArcadeCard glowColor="orange" hover className="text-center">
        <LivePulse className="mb-2 justify-center" />
        <p className="font-pixel text-[10px] text-foreground">
          {match.fighter_a_name ?? "Fighter A"} vs {match.fighter_b_name ?? "Fighter B"}
        </p>
        <Link href={`/arena/${match.id}`} className="mt-3 inline-block">
          <ArcadeButton variant="primary" size="sm" glow>WATCH NOW</ArcadeButton>
        </Link>
      </ArcadeCard>
    </section>
  );
}
