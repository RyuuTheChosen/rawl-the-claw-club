"use client";

import { useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { MatchDataMessage } from "@/types";

interface BettingPanelProps {
  matchId: string;
  data: MatchDataMessage | null;
}

export function BettingPanel({ matchId, data }: BettingPanelProps) {
  const { connected } = useWallet();
  const [side, setSide] = useState<"a" | "b">("a");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePlaceBet = async () => {
    if (!connected || !amount) return;
    setSubmitting(true);
    setError(null);
    try {
      // Bet placement happens via Solana transaction
      // The frontend builds the tx and signs with wallet
      const { placeBetTransaction } = await import("@/lib/solana");
      await placeBetTransaction(matchId, side, parseFloat(amount));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to place bet");
    } finally {
      setSubmitting(false);
    }
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

  return (
    <div className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-rawl-light/80">Place Bet</h3>

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

      {error && (
        <div className="mb-3 text-xs text-red-400">{error}</div>
      )}

      <button
        onClick={handlePlaceBet}
        disabled={submitting || !amount}
        className="w-full rounded bg-rawl-accent py-2 text-sm font-semibold text-rawl-dark transition hover:bg-rawl-accent/80 disabled:opacity-50"
      >
        {submitting ? "Placing..." : "Place Bet"}
      </button>

      {poolTotal > 0 && (
        <div className="mt-2 text-center text-xs text-rawl-light/40">
          Pool: {(poolTotal / 1e9).toFixed(2)} SOL
        </div>
      )}
    </div>
  );
}
