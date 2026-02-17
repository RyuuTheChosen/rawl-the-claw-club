"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import bs58 from "bs58";
import Link from "next/link";
import { Swords } from "lucide-react";
import { Fighter, PretrainedModel } from "@/types";
import { useWalletStore } from "@/stores/walletStore";
import * as gateway from "@/lib/gateway";
import { getFighters, getPretrainedModels } from "@/lib/api";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeButton } from "@/components/ArcadeButton";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { StatusBadge } from "@/components/StatusBadge";
import { DivisionBadge } from "@/components/DivisionBadge";
import { PageTransition } from "@/components/PageTransition";
import { StaggeredList } from "@/components/StaggeredList";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
    return <ArcadeLoader text="LOADING MODELS" />;
  }

  if (models.length === 0) {
    return (
      <div className="py-4 text-center">
        <span className="font-pixel text-[10px] text-muted-foreground">
          NO MODELS AVAILABLE
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block font-pixel text-[8px] text-muted-foreground">
          MODEL
        </label>
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {models.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.name} ({m.character})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selected && (
          <p className="mt-1 text-xs text-muted-foreground">{selected.description}</p>
        )}
      </div>
      <div>
        <label className="mb-1 block font-pixel text-[8px] text-muted-foreground">
          FIGHTER NAME
        </label>
        <Input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. MyFirstBot"
          maxLength={64}
        />
      </div>
      {error && (
        <p className="font-pixel text-[8px] text-neon-red">{error}</p>
      )}
      <ArcadeButton
        onClick={handleAdopt}
        disabled={adopting || !name.trim() || !selectedId}
        glow
        className="w-full"
      >
        {adopting ? "DEPLOYING..." : "DEPLOY FIGHTER"}
      </ArcadeButton>
    </div>
  );
}

function RegisterBanner({ onRegistered }: { onRegistered: () => void }) {
  const { publicKey, signMessage } = useWallet();
  const { setApiKey, setWalletAddress } = useWalletStore();
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState("");

  const handleRegister = async () => {
    if (!publicKey || !signMessage) return;
    setRegistering(true);
    setError("");
    try {
      const message = `Sign to register with Rawl: ${Date.now()}`;
      const encoded = new TextEncoder().encode(message);
      const signatureBytes = await signMessage(encoded);
      const signature = bs58.encode(signatureBytes);
      const walletAddress = publicKey.toBase58();

      const res = await gateway.register(walletAddress, signature, message);
      setApiKey(res.api_key);
      setWalletAddress(walletAddress);
      onRegistered();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  };

  return (
    <ArcadeCard className="mb-6" hover={false} glowColor="orange">
      <h3 className="mb-1 font-pixel text-xs">REGISTER WALLET</h3>
      <p className="mb-3 text-sm text-muted-foreground">
        Sign a message to register your wallet and get an API key. Required before deploying fighters.
      </p>
      {error && <p className="mb-2 font-pixel text-[8px] text-neon-red">{error}</p>}
      <ArcadeButton
        onClick={handleRegister}
        disabled={registering || !signMessage}
        glow
        className="w-full"
      >
        {registering ? "SIGNING..." : "REGISTER"}
      </ArcadeButton>
    </ArcadeCard>
  );
}

export default function DashboardPage() {
  const { connected, publicKey } = useWallet();
  const { apiKey } = useWalletStore();
  const [fighters, setFighters] = useState<Fighter[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdoptForm, setShowAdoptForm] = useState(false);

  const walletAddress = publicKey?.toBase58();

  const refreshFighters = () => {
    if (!walletAddress) return;
    getFighters({ owner: walletAddress })
      .then((res) => setFighters(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!connected || !walletAddress) {
      setLoading(false);
      return;
    }
    refreshFighters();
  }, [connected, walletAddress]);

  if (!connected) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <span className="font-pixel text-sm text-neon-orange text-glow-orange">
          CONNECT WALLET TO ENTER
        </span>
        <span className="text-xs text-muted-foreground">
          Link your Solana wallet to access the dashboard
        </span>
      </div>
    );
  }

  const [queuedIds, setQueuedIds] = useState<Set<string>>(new Set());
  const [queuingId, setQueuingId] = useState<string | null>(null);

  const handleQueue = async (fighter: Fighter) => {
    if (!apiKey) return;
    setQueuingId(fighter.id);
    try {
      await gateway.queueForMatch(apiKey, {
        fighter_id: fighter.id,
        game_id: fighter.game_id,
      });
      setQueuedIds((prev) => new Set(prev).add(fighter.id));
    } catch (err) {
      console.error("Queue failed:", err);
    } finally {
      setQueuingId(null);
    }
  };

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="font-pixel text-base text-neon-orange text-glow-orange sm:text-lg">
              DASHBOARD
            </h1>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {publicKey?.toBase58().slice(0, 8)}...{publicKey?.toBase58().slice(-4)}
            </p>
          </div>
          {fighters.length > 0 && (
            <ArcadeButton
              variant={showAdoptForm ? "ghost" : "outline"}
              size="sm"
              onClick={() => setShowAdoptForm(!showAdoptForm)}
            >
              {showAdoptForm ? "Cancel" : "Deploy Baseline"}
            </ArcadeButton>
          )}
        </div>

        {!apiKey && <RegisterBanner onRegistered={refreshFighters} />}

        {showAdoptForm && fighters.length > 0 && (
          <ArcadeCard className="mb-6" hover={false}>
            <h3 className="mb-3 font-pixel text-[10px]">DEPLOY BASELINE FIGHTER</h3>
            <AdoptForm
              apiKey={apiKey}
              onAdopted={() => {
                setShowAdoptForm(false);
                refreshFighters();
              }}
            />
          </ArcadeCard>
        )}

        <h2 className="mb-4 font-pixel text-xs text-foreground">YOUR FIGHTERS</h2>

        {loading ? (
          <ArcadeLoader text="LOADING FIGHTERS" />
        ) : fighters.length === 0 ? (
          <ArcadeCard hover={false} glowColor="orange">
            <h3 className="mb-1 font-pixel text-xs">DEPLOY A STARTER</h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Pick a pretrained baseline model and deploy it as your fighter.
              It will go straight into calibration to get an Elo rating.
            </p>
            <AdoptForm apiKey={apiKey} onAdopted={refreshFighters} />
          </ArcadeCard>
        ) : (
          <StaggeredList className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {fighters.map((fighter) => (
              <ArcadeCard key={fighter.id}>
                <div className="mb-2 flex items-start justify-between">
                  <Link
                    href={`/fighters/${fighter.id}`}
                    className="font-medium text-neon-orange hover:text-glow-orange hover:underline"
                  >
                    {fighter.name}
                  </Link>
                  <StatusBadge status={fighter.status} />
                </div>
                <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-pixel text-[8px] uppercase">{fighter.game_id}</span>
                  <span>{fighter.character}</span>
                </div>
                <DivisionBadge division={fighter.division_tier} className="mb-3" />

                <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
                  <div>
                    <div className="font-mono text-neon-orange">{fighter.elo_rating.toFixed(0)}</div>
                    <div className="font-pixel text-[7px] text-muted-foreground">ELO</div>
                  </div>
                  <div>
                    <div className="font-mono text-neon-green">{fighter.wins}</div>
                    <div className="font-pixel text-[7px] text-muted-foreground">WINS</div>
                  </div>
                  <div>
                    <div className="font-mono text-neon-red">{fighter.losses}</div>
                    <div className="font-pixel text-[7px] text-muted-foreground">LOSSES</div>
                  </div>
                </div>

                {fighter.status === "ready" && (
                  queuedIds.has(fighter.id) ? (
                    <div className="w-full rounded border border-neon-green/30 bg-neon-green/10 py-1.5 text-center font-pixel text-[9px] text-neon-green">
                      IN QUEUE — WAITING FOR OPPONENT
                    </div>
                  ) : (
                    <ArcadeButton
                      onClick={() => handleQueue(fighter)}
                      disabled={queuingId === fighter.id}
                      variant="outline"
                      size="sm"
                      className="w-full"
                    >
                      <Swords className="mr-1.5 h-3 w-3" />
                      {queuingId === fighter.id ? "QUEUING..." : "Queue for Match"}
                    </ArcadeButton>
                  )
                )}
              </ArcadeCard>
            ))}
          </StaggeredList>
        )}
      </div>
    </PageTransition>
  );
}
