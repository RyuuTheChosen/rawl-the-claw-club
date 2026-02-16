"use client";

import { useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { MatchDataMessage } from "@/types";
import { usePlaceBet, useClaimPayout, useRefundBet } from "@/hooks/useBetting";

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
      <div className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4 text-center text-sm text-rawl-light/50">
        Connect wallet to place bets
      </div>
    );
  }

  const poolTotal = data?.pool_total ?? 0;
  const oddsA = data?.odds_a ?? 1;
  const oddsB = data?.odds_b ?? 1;
  const isOpen = !matchStatus || matchStatus === "open";
  const isResolved = matchStatus === "resolved";
  const isCancelled = matchStatus === "cancelled";

  return (
    <div className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-rawl-light/80">Place Bet</h3>

      {isOpen && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => setSide("a")}
              className={`rounded px-3 py-2 text-sm font-medium transition ${
                side === "a"
                  ? "bg-rawl-primary text-rawl-dark"
                  : "bg-rawl-dark/80 text-rawl-light/60 hover:bg-rawl-dark"
              }`}
            >
              Player 1 ({oddsA.toFixed(2)}x)
            </button>
            <button
              onClick={() => setSide("b")}
              className={`rounded px-3 py-2 text-sm font-medium transition ${
                side === "b"
                  ? "bg-rawl-secondary text-rawl-dark"
                  : "bg-rawl-dark/80 text-rawl-light/60 hover:bg-rawl-dark"
              }`}
            >
              Player 2 ({oddsB.toFixed(2)}x)
            </button>
          </div>

          <div className="mb-3">
            <label className="mb-1 block text-xs text-rawl-light/50">Amount (SOL)</label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full rounded border border-rawl-dark/30 bg-rawl-dark px-3 py-2 text-sm text-rawl-light placeholder-rawl-light/30 focus:border-rawl-primary focus:outline-none"
            />
          </div>

          {amount && (
            <div className="mb-3 text-xs text-rawl-light/50">
              Potential payout:{" "}
              <span className="font-mono text-rawl-primary">
                {(parseFloat(amount) * (side === "a" ? oddsA : oddsB)).toFixed(2)} SOL
              </span>
            </div>
          )}

          <button
            onClick={handlePlaceBet}
            disabled={submitting || !amount}
            className="w-full rounded bg-rawl-accent py-2 text-sm font-semibold text-rawl-dark transition hover:bg-rawl-accent/80 disabled:opacity-50"
          >
            {submitting ? "Placing..." : "Place Bet"}
          </button>
        </>
      )}

      {isResolved && (
        <button
          onClick={handleClaim}
          disabled={claiming}
          className="w-full rounded bg-green-600 py-2 text-sm font-semibold text-white transition hover:bg-green-500 disabled:opacity-50"
        >
          {claiming ? "Claiming..." : "Claim Payout"}
        </button>
      )}

      {isCancelled && (
        <button
          onClick={handleRefund}
          disabled={refunding}
          className="w-full rounded bg-yellow-600 py-2 text-sm font-semibold text-rawl-dark transition hover:bg-yellow-500 disabled:opacity-50"
        >
          {refunding ? "Refunding..." : "Refund Bet"}
        </button>
      )}

      {(error || claimError || refundError) && (
        <div className="mt-3 text-xs text-red-400">{error || claimError || refundError}</div>
      )}

      {txSignature && (
        <div className="mt-2 text-center text-xs text-rawl-light/40">
          Tx: {txSignature.slice(0, 16)}...
        </div>
      )}

      {poolTotal > 0 && (
        <div className="mt-2 text-center text-xs text-rawl-light/40">
          Pool: {(poolTotal / 1e9).toFixed(2)} SOL
        </div>
      )}
    </div>
  );
}
