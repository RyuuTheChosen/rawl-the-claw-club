"use client";

import { useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { MatchDataMessage } from "@/types";
import { usePlaceBet, useClaimPayout, useRefundBet } from "@/hooks/useBetting";
import { ArcadeCard } from "./ArcadeCard";
import { ArcadeButton } from "./ArcadeButton";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface BettingPanelProps {
  matchId: string;
  data: MatchDataMessage | null;
  matchStatus?: string;
}

export function BettingPanel({ matchId, data, matchStatus }: BettingPanelProps) {
  const { connected } = useWallet();
  const [side, setSide] = useState<"a" | "b">("a");
  const [amount, setAmount] = useState("");
  const { placeBet, submitting, error } = usePlaceBet();
  const { claimPayout, submitting: claiming, error: claimError } = useClaimPayout();
  const { refundBet, submitting: refunding, error: refundError } = useRefundBet();
  const [txSignature, setTxSignature] = useState<string | null>(null);

  const handlePlaceBet = async () => {
    if (!connected || !amount) return;
    const sig = await placeBet(matchId, side, parseFloat(amount));
    if (sig) {
      setTxSignature(sig);
      setAmount("");
    }
  };

  const handleClaim = async () => {
    const sig = await claimPayout(matchId);
    if (sig) setTxSignature(sig);
  };

  const handleRefund = async () => {
    const sig = await refundBet(matchId);
    if (sig) setTxSignature(sig);
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

  return (
    <ArcadeCard hover={false}>
      <h3 className="mb-3 font-pixel text-[10px] text-foreground">PLACE BET</h3>

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
        <ArcadeButton
          onClick={handleClaim}
          disabled={claiming}
          variant="primary"
          className="w-full bg-neon-green text-background hover:bg-neon-green/90"
        >
          {claiming ? "CLAIMING..." : "CLAIM PAYOUT"}
        </ArcadeButton>
      )}

      {isCancelled && (
        <ArcadeButton
          onClick={handleRefund}
          disabled={refunding}
          variant="primary"
          className="w-full bg-neon-yellow text-background hover:bg-neon-yellow/90"
        >
          {refunding ? "REFUNDING..." : "REFUND BET"}
        </ArcadeButton>
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
