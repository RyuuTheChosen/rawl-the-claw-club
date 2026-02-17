"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import Link from "next/link";
import { Fighter, PretrainedModel } from "@/types";
import { useWalletStore } from "@/stores/walletStore";
import * as gateway from "@/lib/gateway";
import { getFighters, getPretrainedModels } from "@/lib/api";

function AdoptForm({
  apiKey,
  onAdopted,
}: {
  apiKey: string | null;
  onAdopted: () => void;
}) {
  const [models, setModels] = useState<PretrainedModel[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [name, setName] = useState("");
  const [adopting, setAdopting] = useState(false);
  const [error, setError] = useState("");
  const [loadingModels, setLoadingModels] = useState(true);

  useEffect(() => {
    getPretrainedModels()
      .then((list) => {
        setModels(list);
        if (list.length > 0) setSelectedId(list[0].id);
      })
      .catch(() => setError("Failed to load pretrained models"))
      .finally(() => setLoadingModels(false));
  }, []);

  const selected = models.find((m) => m.id === selectedId);

  const handleAdopt = async () => {
    if (!apiKey) {
      setError("Register your wallet first to get an API key");
      return;
    }
    if (!selectedId || !name.trim()) return;

    setAdopting(true);
    setError("");
    try {
      await gateway.adoptPretrained(apiKey, {
        pretrained_id: selectedId,
        name: name.trim(),
      });
      setName("");
      onAdopted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adopt failed");
    } finally {
      setAdopting(false);
    }
  };

  if (loadingModels) {
    return <div className="py-4 text-center text-sm text-rawl-light/50">Loading models...</div>;
  }

  if (models.length === 0) {
    return (
      <div className="py-4 text-center text-sm text-rawl-light/50">
        No pretrained models available
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-xs text-rawl-light/40">Model</label>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="w-full rounded border border-rawl-dark/30 bg-rawl-dark/80 px-3 py-2 text-sm text-rawl-light"
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.character})
            </option>
          ))}
        </select>
        {selected && (
          <p className="mt-1 text-xs text-rawl-light/30">{selected.description}</p>
        )}
      </div>
      <div>
        <label className="mb-1 block text-xs text-rawl-light/40">Fighter Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. MyFirstBot"
          maxLength={64}
          className="w-full rounded border border-rawl-dark/30 bg-rawl-dark/80 px-3 py-2 text-sm text-rawl-light placeholder:text-rawl-light/20"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        onClick={handleAdopt}
        disabled={adopting || !name.trim() || !selectedId}
        className="w-full rounded bg-rawl-primary py-2 text-sm font-medium text-rawl-dark transition hover:bg-rawl-primary/80 disabled:opacity-50"
      >
        {adopting ? "Deploying..." : "Deploy Fighter"}
      </button>
    </div>
  );
}

export default function DashboardPage() {
  const { connected, publicKey } = useWallet();
  const { apiKey } = useWalletStore();
  const [fighters, setFighters] = useState<Fighter[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdoptForm, setShowAdoptForm] = useState(false);

  const refreshFighters = () => {
    getFighters()
      .then((res) => setFighters(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!connected) {
      setLoading(false);
      return;
    }
    refreshFighters();
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
        {fighters.length > 0 && (
          <button
            onClick={() => setShowAdoptForm(!showAdoptForm)}
            className="rounded border border-rawl-primary/30 px-3 py-1.5 text-xs font-medium text-rawl-primary transition hover:bg-rawl-primary/10"
          >
            {showAdoptForm ? "Cancel" : "Deploy Baseline"}
          </button>
        )}
      </div>

      {showAdoptForm && fighters.length > 0 && (
        <div className="mb-6 rounded-lg border border-rawl-primary/20 bg-rawl-dark/50 p-4">
          <h3 className="mb-3 text-sm font-semibold">Deploy a Baseline Fighter</h3>
          <AdoptForm
            apiKey={apiKey}
            onAdopted={() => {
              setShowAdoptForm(false);
              refreshFighters();
            }}
          />
        </div>
      )}

      <h2 className="mb-4 text-lg font-semibold">Your Fighters</h2>

      {loading ? (
        <div className="py-8 text-center text-rawl-light/50">Loading...</div>
      ) : fighters.length === 0 ? (
        <div className="rounded-lg border border-rawl-primary/20 bg-rawl-dark/50 p-6">
          <h3 className="mb-1 text-lg font-semibold">Deploy a Starter Fighter</h3>
          <p className="mb-4 text-sm text-rawl-light/40">
            Pick a pretrained baseline model and deploy it as your fighter. It will go
            straight into calibration to get an Elo rating.
          </p>
          <AdoptForm apiKey={apiKey} onAdopted={refreshFighters} />
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
                      : fighter.status === "calibrating"
                        ? "bg-blue-500/20 text-blue-400"
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
