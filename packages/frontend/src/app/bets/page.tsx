"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useWallet } from "@solana/wallet-adapter-react";
import { Bet } from "@/types";
import { getBets, syncBetStatus } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { useClaimPayout, useRefundBet } from "@/hooks/useBetting";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeButton } from "@/components/ArcadeButton";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { StatusBadge } from "@/components/StatusBadge";
import { PageTransition } from "@/components/PageTransition";
import { StaggeredList } from "@/components/StaggeredList";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type FilterTab = "all" | "active" | "claimable" | "history";
const FILTERS: FilterTab[] = ["all", "active", "claimable", "history"];

function isActive(bet: Bet): boolean {
  return bet.status === "confirmed" && (bet.match_status === "open" || bet.match_status === "locked");
}

function isClaimable(bet: Bet): boolean {
  if (bet.status !== "confirmed") return false;
  if (bet.match_status === "cancelled") return true;
  if (bet.match_status === "resolved") {
    // Won if their side's fighter is the winner
    const wonSide = bet.side === "a" ? bet.match_winner_id === null : false;
    // Actually, we need to check fighter IDs — but we don't have them in Bet.
    // Simpler: if match resolved and bet confirmed, user may have won (show claim option)
    return true;
  }
  return false;
}

function isHistory(bet: Bet): boolean {
  return bet.status === "claimed" || bet.status === "refunded" || bet.status === "expired";
}

function filterBets(bets: Bet[], tab: FilterTab): Bet[] {
  switch (tab) {
    case "active":
      return bets.filter(isActive);
    case "claimable":
      return bets.filter(isClaimable);
    case "history":
      return bets.filter(isHistory);
    default:
      return bets;
  }
}

function BetCard({
  bet,
  onStatusChange,
}: {
  bet: Bet;
  onStatusChange: () => void;
}) {
  const { publicKey } = useWallet();
  const { claimPayout, submitting: claiming } = useClaimPayout();
  const { refundBet, submitting: refunding } = useRefundBet();
  const [syncing, setSyncing] = useState(false);

  const sideLabel = bet.side === "a" ? "P1" : "P2";
  const fighterName =
    bet.side === "a"
      ? bet.fighter_a_name ?? "P1"
      : bet.fighter_b_name ?? "P2";

  const handleRefund = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const sig = await refundBet(bet.match_id, bet.id);
    if (sig) {
      setSyncing(true);
      try {
        if (publicKey) await syncBetStatus(bet.id, publicKey.toBase58());
      } catch { /* non-critical */ }
      setSyncing(false);
      onStatusChange();
    }
  };

  const handleClaim = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const sig = await claimPayout(bet.match_id, bet.id);
    if (sig) {
      setSyncing(true);
      try {
        if (publicKey) await syncBetStatus(bet.id, publicKey.toBase58());
      } catch { /* non-critical */ }
      setSyncing(false);
      onStatusChange();
    }
  };

  const renderAction = () => {
    // Already settled
    if (bet.status === "refunded") {
      return (
        <span className="font-pixel text-[8px] text-neon-green">REFUNDED</span>
      );
    }
    if (bet.status === "claimed") {
      return (
        <span className="font-pixel text-[8px] text-neon-green">CLAIMED</span>
      );
    }
    if (bet.status === "expired") {
      return (
        <span className="font-pixel text-[8px] text-muted-foreground">EXPIRED</span>
      );
    }

    // Confirmed + cancelled → refund
    if (bet.status === "confirmed" && bet.match_status === "cancelled") {
      return (
        <ArcadeButton
          size="sm"
          onClick={handleRefund}
          disabled={refunding || syncing}
          className="bg-neon-yellow text-background hover:bg-neon-yellow/90"
        >
          {refunding ? "REFUNDING..." : syncing ? "SYNCING..." : "REFUND"}
        </ArcadeButton>
      );
    }

    // Confirmed + resolved → claim (user may have won)
    if (bet.status === "confirmed" && bet.match_status === "resolved") {
      return (
        <ArcadeButton
          size="sm"
          onClick={handleClaim}
          disabled={claiming || syncing}
          className="bg-neon-green text-background hover:bg-neon-green/90"
        >
          {claiming ? "CLAIMING..." : syncing ? "SYNCING..." : "CLAIM PAYOUT"}
        </ArcadeButton>
      );
    }

    // Active bet
    if (bet.status === "confirmed" && (bet.match_status === "open" || bet.match_status === "locked")) {
      return (
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 animate-pulse rounded-full bg-neon-green" />
          <span className="font-pixel text-[8px] text-neon-green">ACTIVE</span>
        </div>
      );
    }

    return null;
  };

  return (
    <Link href={`/arena/${bet.match_id}`}>
      <ArcadeCard className="flex flex-col gap-2">
        {/* Top: game + match status */}
        <div className="flex items-center justify-between">
          <span className="font-pixel text-[8px] uppercase tracking-wider text-muted-foreground">
            {bet.game_id}
          </span>
          <StatusBadge status={bet.match_status} />
        </div>

        {/* Fighters */}
        <div className="flex items-center justify-between">
          <span
            className={cn(
              "font-mono text-sm",
              bet.side === "a" ? "text-neon-cyan" : "text-muted-foreground",
            )}
          >
            {bet.fighter_a_name ?? "P1"}
          </span>
          <span className="font-pixel text-[8px] text-muted-foreground">VS</span>
          <span
            className={cn(
              "font-mono text-sm",
              bet.side === "b" ? "text-neon-pink" : "text-muted-foreground",
            )}
          >
            {bet.fighter_b_name ?? "P2"}
          </span>
        </div>

        {/* Bet info */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            <span className="font-mono text-neon-orange">{bet.amount_sol.toFixed(2)} SOL</span>
            {" on "}
            <span className={cn("font-semibold", bet.side === "a" ? "text-neon-cyan" : "text-neon-pink")}>
              {sideLabel}
            </span>
          </span>
          {renderAction()}
        </div>

        {/* Timestamp */}
        <div className="text-right font-mono text-[10px] text-muted-foreground/60">
          {new Date(bet.created_at).toLocaleDateString()}
        </div>
      </ArcadeCard>
    </Link>
  );
}

export default function BetsPage() {
  const { connected, publicKey } = useWallet();
  const [tab, setTab] = useState<string>("all");

  const wallet = publicKey?.toBase58() ?? "";

  const fetcher = useCallback((): Promise<Bet[]> => {
    if (!wallet) return Promise.resolve([]);
    return getBets(wallet);
  }, [wallet]);

  const { data: bets, isPolling, refresh } = usePolling({
    fetcher,
    interval: 10_000,
    enabled: connected && !!wallet,
    key: wallet,
  });

  if (!connected) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <span className="font-pixel text-sm text-neon-orange text-glow-orange">
          CONNECT WALLET TO VIEW BETS
        </span>
        <span className="text-xs text-muted-foreground">
          Link your Solana wallet to see your betting history
        </span>
      </div>
    );
  }

  const allBets = bets ?? [];
  const filtered = filterBets(allBets, tab as FilterTab);

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <h1 className="font-pixel text-base text-neon-orange text-glow-orange sm:text-lg">
              MY BETS
            </h1>
            {isPolling && (
              <span className="h-2 w-2 animate-pulse rounded-full bg-neon-green" />
            )}
          </div>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              {FILTERS.map((f) => (
                <TabsTrigger key={f} value={f} className="font-pixel text-[8px] uppercase">
                  {f}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        {bets === null ? (
          <ArcadeLoader text="LOADING BETS" />
        ) : filtered.length === 0 ? (
          <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2">
            <span className="font-pixel text-sm text-muted-foreground">
              NO BETS FOUND
            </span>
            <span className="text-xs text-muted-foreground/60">
              {tab === "all"
                ? "Place your first bet from the arena"
                : "No bets match this filter"}
            </span>
          </div>
        ) : (
          <StaggeredList className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((bet) => (
              <BetCard key={bet.id} bet={bet} onStatusChange={refresh} />
            ))}
          </StaggeredList>
        )}
      </div>
    </PageTransition>
  );
}
