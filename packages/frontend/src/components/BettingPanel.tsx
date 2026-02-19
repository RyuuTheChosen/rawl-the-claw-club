"use client";

import { useEffect, useState } from "react";
import { useAccount } from "wagmi";
import { Bet, MatchDataMessage } from "@/types";
import { getBets, syncBetStatus } from "@/lib/api";
import { usePlaceBet, useClaimPayout, useRefundBet } from "@/hooks/useBetting";
import { ArcadeCard } from "./ArcadeCard";
import { ArcadeButton } from "./ArcadeButton";
import { Countdown } from "./Countdown";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface BettingPanelProps {
  matchId: string;
  data: MatchDataMessage | null;
  matchStatus?: string;
  startsAt?: string | null;
  winningSide?: "a" | "b" | null;
}

export function BettingPanel({ matchId, data, matchStatus, startsAt, winningSide = null }: BettingPanelProps) {
  const { isConnected, address } = useAccount();
  const [side, setSide] = useState<"a" | "b">("a");
  const [amount, setAmount] = useState("");
  const { placeBet, submitting, error } = usePlaceBet();
  const { claimPayout, submitting: claiming, error: claimError } = useClaimPayout();
  const { refundBet, submitting: refunding, error: refundError } = useRefundBet();
  const [txHash, setTxHash] = useState<string | null>(null);
  const [existingBet, setExistingBet] = useState<Bet | null>(null);
  const [loadingBet, setLoadingBet] = useState(false);

  // Fetch existing bet for this match
  useEffect(() => {
    if (!isConnected || !address) {
      setExistingBet(null);
      return;
    }
    let cancelled = false;
    setLoadingBet(true);
    getBets(address, matchId)
      .then((bets) => {
        if (!cancelled) setExistingBet(bets.length > 0 ? bets[0] : null);
      })
      .catch(() => {
        if (!cancelled) setExistingBet(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingBet(false);
      });
    return () => { cancelled = true; };
  }, [isConnected, address, matchId]);

  const refreshBet = async () => {
    if (!address) return;
    try {
      const bets = await getBets(address, matchId);
      setExistingBet(bets.length > 0 ? bets[0] : null);
    } catch { /* ignore */ }
  };

  const handlePlaceBet = async () => {
    if (!isConnected || !amount) return;
    const hash = await placeBet(matchId, side, parseFloat(amount));
    if (hash) {
      setTxHash(hash);
      setAmount("");
      toast.success("Bet placed!", { description: `TX: ${hash.slice(0, 16)}...` });
      // Refresh to show existing bet
      setTimeout(refreshBet, 1000);
    }
  };

  const handleClaim = async () => {
    const hash = await claimPayout(matchId, existingBet?.id);
    if (hash) {
      setTxHash(hash);
      toast.success("Payout claimed!");
      // Optimistically update local state — tx succeeded on-chain
      setExistingBet((prev) => prev ? { ...prev, status: "claimed" } : null);
      // Sync with backend after a delay
      if (existingBet && address) {
        const betId = existingBet.id;
        setTimeout(async () => {
          try { await syncBetStatus(betId, address); } catch { /* non-critical */ }
        }, 3000);
      }
    }
  };

  const handleRefund = async () => {
    const hash = await refundBet(matchId, existingBet?.id);
    if (hash) {
      setTxHash(hash);
      toast.success("Bet refunded!");
      // Optimistically update local state — tx succeeded on-chain
      setExistingBet((prev) => prev ? { ...prev, status: "refunded" } : null);
      // Sync with backend after a delay
      if (existingBet && address) {
        const betId = existingBet.id;
        setTimeout(async () => {
          try { await syncBetStatus(betId, address); } catch { /* non-critical */ }
        }, 3000);
      }
    }
  };

  if (!isConnected) {
    return (
      <ArcadeCard hover={false}>
        <div className="py-4 text-center">
          <span className="font-pixel text-[10px] text-muted-foreground">
            CONNECT WALLET TO BET
          </span>
        </div>
      </ArcadeCard>
    );
  }

  const poolTotal = data?.pool_total ?? 0;
  const oddsA = data?.odds_a ?? 1;
  const oddsB = data?.odds_b ?? 1;
  const isOpen = !matchStatus || matchStatus === "open";
  const isResolved = matchStatus === "resolved";
  const isCancelled = matchStatus === "cancelled";

  // Determine if current user's bet won or lost
  const userWon = existingBet && winningSide ? existingBet.side === winningSide : null;

  // Existing bet display
  if (existingBet) {
    const betSideLabel = existingBet.side === "a" ? "P1" : "P2";
    const betSideColor = existingBet.side === "a" ? "text-neon-cyan" : "text-neon-pink";

    return (
      <ArcadeCard hover={false}>
        <h3 className="mb-3 font-pixel text-[10px] text-foreground">YOUR BET</h3>

        <div className="mb-3 rounded-md bg-muted/50 px-3 py-2.5 text-center">
          <span className="font-mono text-sm text-neon-orange">
            {existingBet.amount_eth.toFixed(4)} ETH
          </span>
          <span className="text-xs text-muted-foreground"> on </span>
          <span className={cn("font-semibold text-sm", betSideColor)}>
            {betSideLabel}
          </span>
        </div>

        {/* Already refunded/claimed */}
        {existingBet.status === "refunded" && (
          <div className="mb-3 rounded-md bg-neon-green/10 py-2 text-center">
            <span className="font-pixel text-[10px] text-neon-green">REFUNDED</span>
          </div>
        )}
        {existingBet.status === "claimed" && (
          <div className="mb-3 rounded-md bg-neon-green/10 py-2 text-center">
            <span className="font-pixel text-[10px] text-neon-green">CLAIMED</span>
          </div>
        )}
        {existingBet.status === "expired" && (
          <div className="mb-3 rounded-md bg-muted/50 py-2 text-center">
            <span className="font-pixel text-[10px] text-muted-foreground">EXPIRED</span>
          </div>
        )}

        {/* Cancelled + confirmed → refund */}
        {isCancelled && existingBet.status === "confirmed" && (
          <ArcadeButton
            onClick={handleRefund}
            disabled={refunding}
            className="w-full bg-neon-yellow text-background hover:bg-neon-yellow/90"
          >
            {refunding ? "REFUNDING..." : "REFUND BET"}
          </ArcadeButton>
        )}

        {/* Resolved + confirmed → claim (winner) or lost (loser) */}
        {isResolved && existingBet.status === "confirmed" && userWon === true && (
          <ArcadeButton
            onClick={handleClaim}
            disabled={claiming}
            variant="primary"
            className="w-full bg-neon-green text-background hover:bg-neon-green/90"
          >
            {claiming ? "CLAIMING..." : "CLAIM PAYOUT"}
          </ArcadeButton>
        )}
        {isResolved && existingBet.status === "confirmed" && userWon === false && (
          <div className="mb-3 rounded-md bg-neon-red/10 py-2 text-center">
            <span className="font-pixel text-[10px] text-neon-red">BET LOST</span>
          </div>
        )}

        {/* Active match — show live indicator */}
        {existingBet.status === "confirmed" && (isOpen || matchStatus === "locked") && (
          <div className="flex items-center justify-center gap-2 py-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-neon-green" />
            <span className="font-pixel text-[10px] text-neon-green">MATCH IN PROGRESS</span>
          </div>
        )}

        {(error || claimError || refundError) && (
          <div className="mt-3 font-pixel text-[10px] text-neon-red">
            {error || claimError || refundError}
          </div>
        )}

        {txHash && (
          <div className="mt-2 text-center font-mono text-[10px] text-muted-foreground">
            TX: {txHash.slice(0, 16)}...
          </div>
        )}

        {poolTotal > 0 && (
          <div className="mt-3 border-t border-border pt-2 text-center">
            <span className="font-pixel text-[10px] text-muted-foreground">TOTAL POOL </span>
            <span className="font-mono text-xs text-neon-orange">
              {(poolTotal / 1e18).toFixed(4)} ETH
            </span>
          </div>
        )}
      </ArcadeCard>
    );
  }

  // No existing bet — show place bet form
  return (
    <ArcadeCard hover={false}>
      <h3 className="mb-3 font-pixel text-[10px] text-foreground">PLACE BET</h3>

      {isOpen && startsAt && (
        <div className="mb-3 flex items-center justify-between rounded-md bg-neon-yellow/10 px-3 py-2">
          <span className="font-pixel text-[10px] text-neon-yellow">MATCH STARTS IN</span>
          <Countdown targetDate={startsAt} />
        </div>
      )}

      {isOpen && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => setSide("a")}
              aria-pressed={side === "a"}
              aria-label="Bet on Player 1"
              className={cn(
                "rounded-md px-3 py-2.5 text-sm font-semibold transition-all",
                side === "a"
                  ? "bg-neon-cyan/20 text-neon-cyan ring-1 ring-neon-cyan/40 shadow-neon-cyan"
                  : "bg-muted text-muted-foreground hover:bg-muted/80",
              )}
            >
              <div className="font-pixel text-[10px]">P1</div>
              <div className="font-mono text-xs">{oddsA.toFixed(2)}x</div>
            </button>
            <button
              onClick={() => setSide("b")}
              aria-pressed={side === "b"}
              aria-label="Bet on Player 2"
              className={cn(
                "rounded-md px-3 py-2.5 text-sm font-semibold transition-all",
                side === "b"
                  ? "bg-neon-pink/20 text-neon-pink ring-1 ring-neon-pink/40 shadow-neon-pink"
                  : "bg-muted text-muted-foreground hover:bg-muted/80",
              )}
            >
              <div className="font-pixel text-[10px]">P2</div>
              <div className="font-mono text-xs">{oddsB.toFixed(2)}x</div>
            </button>
          </div>

          <div className="mb-3">
            <label className="mb-1 block font-pixel text-[10px] text-muted-foreground">
              AMOUNT (ETH)
            </label>
            <Input
              type="number"
              min="0.001"
              step="0.001"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.000"
              className="font-mono"
            />
          </div>

          {amount && (
            <div className="mb-3 text-xs text-muted-foreground">
              Potential payout:{" "}
              <span className="font-mono text-neon-orange">
                {(parseFloat(amount) * (side === "a" ? oddsA : oddsB)).toFixed(4)} ETH
              </span>
            </div>
          )}

          <ArcadeButton
            onClick={handlePlaceBet}
            disabled={submitting || !amount}
            glow
            className="w-full"
          >
            {submitting ? "PLACING..." : "PLACE BET"}
          </ArcadeButton>
        </>
      )}

      {isResolved && (
        <div className="py-4 text-center">
          <span className="font-pixel text-[10px] text-muted-foreground">
            MATCH RESOLVED — NO BET PLACED
          </span>
        </div>
      )}

      {isCancelled && (
        <div className="py-4 text-center">
          <span className="font-pixel text-[10px] text-muted-foreground">
            MATCH CANCELLED
          </span>
        </div>
      )}

      {(error || claimError || refundError) && (
        <div className="mt-3 font-pixel text-[10px] text-neon-red">
          {error || claimError || refundError}
        </div>
      )}

      {txHash && (
        <div className="mt-2 text-center font-mono text-[10px] text-muted-foreground">
          TX: {txHash.slice(0, 16)}...
        </div>
      )}

      {poolTotal > 0 && (
        <div className="mt-3 border-t border-border pt-2 text-center">
          <span className="font-pixel text-[10px] text-muted-foreground">TOTAL POOL </span>
          <span className="font-mono text-xs text-neon-orange">
            {(poolTotal / 1e18).toFixed(4)} ETH
          </span>
        </div>
      )}
    </ArcadeCard>
  );
}
