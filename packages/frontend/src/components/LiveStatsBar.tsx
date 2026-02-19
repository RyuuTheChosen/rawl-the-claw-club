"use client";

import { getStats } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { useAnimatedCounter } from "@/hooks/useAnimatedCounter";
import { LivePulse } from "@/components/LivePulse";

function AnimatedStat({ label, value, suffix }: { label: string; value: number; suffix?: string }) {
  const display = useAnimatedCounter(value);
  return (
    <div className="text-center">
      <div className="font-mono text-lg text-neon-orange">
        {suffix ? `${display}${suffix}` : display}
      </div>
      <div className="font-pixel text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}

export function LiveStatsBar() {
  const { data } = usePolling({ fetcher: getStats, interval: 60_000 });

  if (!data) {
    return (
      <section className="w-full border-t border-border bg-card/50 py-6">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-8 px-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="text-center">
              <div className="mx-auto h-6 w-16 animate-pulse rounded bg-muted" />
              <div className="mx-auto mt-1 h-3 w-12 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  const volumeEth = (data.total_volume_wei / 1e18).toFixed(4);

  return (
    <section className="w-full border-t border-border bg-card/50 py-6">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-8 px-4">
        <AnimatedStat label="MATCHES" value={data.total_matches} />
        <AnimatedStat label="FIGHTERS" value={data.active_fighters} />
        <div className="text-center">
          <div className="font-mono text-lg text-neon-orange">{volumeEth} ETH</div>
          <div className="font-pixel text-[10px] text-muted-foreground">TOTAL WAGERED</div>
        </div>
        {data.live_matches > 0 && (
          <div className="flex items-center gap-2">
            <LivePulse />
            <span className="font-mono text-sm text-muted-foreground">
              {data.live_matches} live now
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
