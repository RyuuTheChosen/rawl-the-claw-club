"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { Bet, MatchDataMessage } from "@/types";
import { getBets, syncBetStatus } from "@/lib/api";
import { usePlaceBet, useClaimPayout, useRefundBet } from "@/hooks/useBetting";
import { ArcadeCard } from "./ArcadeCard";
import { ArcadeButton } from "./ArcadeButton";
import { Countdown } from "./Countdown";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface BettingPanelProps {
  matchId: string;
  data: MatchDataMessage | null;
  matchStatus?: string;
  startsAt?: string | null;
  winningSide?: "a" | "b" | null;
}

export function BettingPanel({ matchId, data, matchStatus, startsAt, winningSide = null }: BettingPanelProps) {
  const { connected, publicKey } = useWallet();
  const [side, setSide] = useState<"a" | "b">("a");
  const [amount, setAmount] = useState("");
  const { placeBet, submitting, error } = usePlaceBet();
  const { claimPayout, submitting: claiming, error: claimError } = useClaimPayout();
  const { refundBet, submitting: refunding, error: refundError } = useRefundBet();
  const [txSignature, setTxSignature] = useState<string | null>(null);
  const [existingBet, setExistingBet] = useState<Bet | null>(null);
  const [loadingBet, setLoadingBet] = useState(false);

  // Fetch existing bet for this match
  useEffect(() => {
    if (!connected || !publicKey) {
      setExistingBet(null);
      return;
    }
    let cancelled = false;
    setLoadingBet(true);
    getBets(publicKey.toBase58(), matchId)
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
  }, [connected, publicKey, matchId]);

  const refreshBet = async () => {
    if (!publicKey) return;
    try {
      const bets = await getBets(publicKey.toBase58(), matchId);
      setExistingBet(bets.length > 0 ? bets[0] : null);
    } catch { /* ignore */ }
  };

  const handlePlaceBet = async () => {
    if (!connected || !amount) return;
    const sig = await placeBet(matchId, side, parseFloat(amount));
    if (sig) {
      setTxSignature(sig);
      setAmount("");
      // Refresh to show existing bet
      setTimeout(refreshBet, 1000);
    }
  };

  const handleClaim = async () => {
    const sig = await claimPayout(matchId, existingBet?.id);
    if (sig) {
      setTxSignature(sig);
      // Optimistically update local state — tx succeeded on-chain
      setExistingBet((prev) => prev ? { ...prev, status: "claimed" } : null);
      // Sync with backend after a delay (RPC needs time to reflect PDA closure)
      if (existingBet && publicKey) {
        const betId = existingBet.id;
        const wallet = publicKey.toBase58();
        setTimeout(async () => {
          try { await syncBetStatus(betId, wallet); } catch { /* non-critical */ }
        }, 3000);
      }
    }
  };

  const handleRefund = async () => {
    const sig = await refundBet(matchId, existingBet?.id);
    if (sig) {
      setTxSignature(sig);
      // Optimistically update local state — tx succeeded on-chain
      setExistingBet((prev) => prev ? { ...prev, status: "refunded" } : null);
      // Sync with backend after a delay (RPC needs time to reflect PDA closure)
      if (existingBet && publicKey) {
        const betId = existingBet.id;
        const wallet = publicKey.toBase58();
        setTimeout(async () => {
          try { await syncBetStatus(betId, wallet); } catch { /* non-critical */ }
        }, 3000);
      }
    }
  };

  if (!connected) {
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
            {existingBet.amount_sol.toFixed(2)} SOL
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
            <span className="font-pixel text-[8px] text-neon-green">MATCH IN PROGRESS</span>
          </div>
        )}

        {(error || claimError || refundError) && (
          <div className="mt-3 font-pixel text-[8px] text-neon-red">
            {error || claimError || refundError}
          </div>
        )}

        {txSignature && (
          <div className="mt-2 text-center font-mono text-[10px] text-muted-foreground">
            TX: {txSignature.slice(0, 16)}...
          </div>
        )}

        {poolTotal > 0 && (
          <div className="mt-3 border-t border-border pt-2 text-center">
            <span className="font-pixel text-[8px] text-muted-foreground">TOTAL POOL </span>
            <span className="font-mono text-xs text-neon-orange">
              {(poolTotal / 1e9).toFixed(2)} SOL
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
          <span className="font-pixel text-[8px] text-neon-yellow">MATCH STARTS IN</span>
          <Countdown targetDate={startsAt} />
        </div>
      )}

      {isOpen && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => setSide("a")}
              className={cn(
                "rounded-md px-3 py-2.5 text-sm font-semibold transition-all",
                side === "a"
                  ? "bg-neon-cyan/20 text-neon-cyan ring-1 ring-neon-cyan/40 shadow-neon-cyan"
                  : "bg-muted text-muted-foreground hover:bg-muted/80",
              )}
            >
              <div className="font-pixel text-[8px]">P1</div>
              <div className="font-mono text-xs">{oddsA.toFixed(2)}x</div>
            </button>
            <button
              onClick={() => setSide("b")}
              className={cn(
                "rounded-md px-3 py-2.5 text-sm font-semibold transition-all",
                side === "b"
                  ? "bg-neon-pink/20 text-neon-pink ring-1 ring-neon-pink/40 shadow-neon-pink"
                  : "bg-muted text-muted-foreground hover:bg-muted/80",
              )}
            >
              <div className="font-pixel text-[8px]">P2</div>
              <div className="font-mono text-xs">{oddsB.toFixed(2)}x</div>
            </button>
          </div>

          <div className="mb-3">
            <label className="mb-1 block font-pixel text-[8px] text-muted-foreground">
              AMOUNT (SOL)
            </label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="font-mono"
            />
          </div>

          {amount && (
            <div className="mb-3 text-xs text-muted-foreground">
              Potential payout:{" "}
              <span className="font-mono text-neon-orange">
                {(parseFloat(amount) * (side === "a" ? oddsA : oddsB)).toFixed(2)} SOL
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
        <div className="mt-3 font-pixel text-[8px] text-neon-red">
          {error || claimError || refundError}
        </div>
      )}

      {txSignature && (
        <div className="mt-2 text-center font-mono text-[10px] text-muted-foreground">
          TX: {txSignature.slice(0, 16)}...
        </div>
      )}

      {poolTotal > 0 && (
        <div className="mt-3 border-t border-border pt-2 text-center">
          <span className="font-pixel text-[8px] text-muted-foreground">TOTAL POOL </span>
          <span className="font-mono text-xs text-neon-orange">
            {(poolTotal / 1e9).toFixed(2)} SOL
          </span>
        </div>
      )}
    </ArcadeCard>
  );
}
