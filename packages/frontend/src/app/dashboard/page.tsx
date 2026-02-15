"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import Link from "next/link";
import { Fighter } from "@/types";
import { useWalletStore } from "@/stores/walletStore";
import * as gateway from "@/lib/gateway";
import { getFighters } from "@/lib/api";

export default function DashboardPage() {
  const { connected, publicKey } = useWallet();
  const { apiKey } = useWalletStore();
  const [fighters, setFighters] = useState<Fighter[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!connected) {
      setLoading(false);
      return;
    }
    getFighters()
      .then((res) => setFighters(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [connected]);

  if (!connected) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold">Dashboard</h1>
          <p className="text-rawl-light/50">Connect your wallet to view your dashboard</p>
        </div>
      </div>
    );
  }

  const handleQueue = async (fighter: Fighter) => {
    if (!apiKey) return;
    try {
      await gateway.queueForMatch(apiKey, {
        fighter_id: fighter.id,
        game_id: fighter.game_id,
      });
    } catch (err) {
      console.error("Queue failed:", err);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-rawl-light/40">
            {publicKey?.toBase58().slice(0, 8)}...{publicKey?.toBase58().slice(-4)}
          </p>
        </div>
      </div>

      <h2 className="mb-4 text-lg font-semibold">Your Fighters</h2>

      {loading ? (
        <div className="py-8 text-center text-rawl-light/50">Loading...</div>
      ) : fighters.length === 0 ? (
        <div className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 py-12 text-center">
          <p className="text-rawl-light/50">No fighters yet</p>
          <p className="mt-1 text-sm text-rawl-light/30">
            Submit a trained model to get started
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {fighters.map((fighter) => (
            <div
              key={fighter.id}
              className="rounded-lg border border-rawl-dark/30 bg-rawl-dark/50 p-4"
            >
              <div className="mb-2 flex items-start justify-between">
                <Link
                  href={`/fighters/${fighter.id}`}
                  className="font-medium text-rawl-primary hover:underline"
                >
                  {fighter.name}
                </Link>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    fighter.status === "ready"
                      ? "bg-green-500/20 text-green-400"
                      : fighter.status === "validating"
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-red-500/20 text-red-400"
                  }`}
                >
                  {fighter.status}
                </span>
              </div>
              <div className="mb-3 text-xs text-rawl-light/40">
                {fighter.game_id.toUpperCase()} - {fighter.character}
              </div>
              <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div>
                  <div className="font-mono text-rawl-primary">
                    {fighter.elo_rating.toFixed(0)}
                  </div>
                  <div className="text-rawl-light/30">Elo</div>
                </div>
                <div>
                  <div className="font-mono text-green-400">{fighter.wins}</div>
                  <div className="text-rawl-light/30">Wins</div>
                </div>
                <div>
                  <div className="font-mono text-red-400">{fighter.losses}</div>
                  <div className="text-rawl-light/30">Losses</div>
                </div>
              </div>
              {fighter.status === "ready" && (
                <button
                  onClick={() => handleQueue(fighter)}
                  className="w-full rounded bg-rawl-primary/20 py-1.5 text-xs font-medium text-rawl-primary transition hover:bg-rawl-primary/30"
                >
                  Queue for Match
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
