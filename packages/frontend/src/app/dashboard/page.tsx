"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import bs58 from "bs58";
import Link from "next/link";
import { Swords, X } from "lucide-react";
import { toast } from "sonner";
import { Fighter, Match, PretrainedModel } from "@/types";
import { useWalletStore } from "@/stores/walletStore";
import * as gateway from "@/lib/gateway";
import { getFighters, getMatches, getPretrainedModels } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeButton } from "@/components/ArcadeButton";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { StatusBadge } from "@/components/StatusBadge";
import { DivisionBadge } from "@/components/DivisionBadge";
import { Countdown } from "@/components/Countdown";
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

interface QueueEntry {
  queuedAt: number;
  error?: string;
  elapsed: number;
  queueSize: number;
}

interface MatchFound {
  matchId: string;
  startsAt: string | null;
}

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
        <label className="mb-1 block font-pixel text-[10px] text-muted-foreground">
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
        <label className="mb-1 block font-pixel text-[10px] text-muted-foreground">
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
        <p className="font-pixel text-[10px] text-neon-red">{error}</p>
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
      {error && <p className="mb-2 font-pixel text-[10px] text-neon-red">{error}</p>}
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

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function DashboardPage() {
  const { connected, publicKey } = useWallet();
  const { apiKey } = useWalletStore();
  const [showAdoptForm, setShowAdoptForm] = useState(false);
  const [queueMap, setQueueMap] = useState<Record<string, QueueEntry>>({});
  const [matchFoundMap, setMatchFoundMap] = useState<Record<string, MatchFound>>({});
  const [queuingId, setQueuingId] = useState<string | null>(null);
  const [leavingId, setLeavingId] = useState<string | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const walletAddress = publicKey?.toBase58();

  // Fighter polling — must be before early return
  const fighterFetcher = useCallback(async () => {
    if (!walletAddress) return [];
    const res = await getFighters({ owner: walletAddress });
    return res.items;
  }, [walletAddress]);

  const {
    data: fighters,
    refresh: refreshFighters,
  } = usePolling<Fighter[]>({
    fetcher: fighterFetcher,
    interval: 10_000,
    enabled: connected && !!walletAddress,
    key: walletAddress ?? "",
  });

  // Tick elapsed counters every second for queued fighters
  useEffect(() => {
    const ids = Object.keys(queueMap);
    if (ids.length === 0) {
      if (tickRef.current) {
        clearInterval(tickRef.current);
        tickRef.current = null;
      }
      return;
    }

    tickRef.current = setInterval(() => {
      setQueueMap((prev) => {
        const next = { ...prev };
        for (const id of Object.keys(next)) {
          next[id] = {
            ...next[id],
            elapsed: (Date.now() - next[id].queuedAt) / 1000,
          };
        }
        return next;
      });
    }, 1000);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [Object.keys(queueMap).length]);

  // Poll queue status + match detection for queued fighters (every 5s)
  useEffect(() => {
    const ids = Object.keys(queueMap);
    if (ids.length === 0 || !apiKey) return;

    const poll = async () => {
      for (const fighterId of ids) {
        try {
          // Check if match was created for this fighter
          const res = await getMatches({ fighter_id: fighterId, limit: 1 });
          if (res.items.length > 0) {
            const match: Match = res.items[0];
            const matchCreated = new Date(match.created_at).getTime();
            const queueEntry = queueMap[fighterId];
            // Only count matches created after queuing
            if (
              (match.status === "open" || match.status === "locked") &&
              queueEntry &&
              matchCreated >= queueEntry.queuedAt - 5000
            ) {
              setMatchFoundMap((prev) => ({
                ...prev,
                [fighterId]: { matchId: match.id, startsAt: match.starts_at },
              }));
              setQueueMap((prev) => {
                const next = { ...prev };
                delete next[fighterId];
                return next;
              });
              continue;
            }
          }

          // Check queue status from backend
          const status = await gateway.getQueueStatus(apiKey, fighterId);
          if (!status.queued) {
            // Fighter was removed from queue (TTL expired or matched)
            setQueueMap((prev) => {
              const next = { ...prev };
              delete next[fighterId];
              return next;
            });
          } else {
            setQueueMap((prev) => ({
              ...prev,
              [fighterId]: {
                ...prev[fighterId],
                queueSize: status.queue_size,
              },
            }));
          }
        } catch {
          // Silently continue polling
        }
      }
    };

    poll();
    const timer = setInterval(poll, 5_000);
    return () => clearInterval(timer);
  }, [Object.keys(queueMap).join(","), apiKey]);

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

  const fighterList = fighters ?? [];
  const loading = fighters === null;

  const handleQueue = async (fighter: Fighter) => {
    if (!apiKey) return;
    setQueuingId(fighter.id);
    try {
      await gateway.queueForMatch(apiKey, {
        fighter_id: fighter.id,
        game_id: fighter.game_id,
      });
      setQueueMap((prev) => ({
        ...prev,
        [fighter.id]: { queuedAt: Date.now(), elapsed: 0, queueSize: 0 },
      }));
      toast.success("Queued for matchmaking!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Queue failed";
      toast.error(msg);
      setQueueMap((prev) => ({
        ...prev,
        [fighter.id]: { queuedAt: Date.now(), elapsed: 0, queueSize: 0, error: msg },
      }));
      // Auto-clear error after 5 seconds
      setTimeout(() => {
        setQueueMap((prev) => {
          const next = { ...prev };
          delete next[fighter.id];
          return next;
        });
      }, 5000);
    } finally {
      setQueuingId(null);
    }
  };

  const handleLeaveQueue = async (fighter: Fighter) => {
    if (!apiKey) return;
    setLeavingId(fighter.id);
    try {
      await gateway.leaveQueue(apiKey, fighter.id);
    } catch {
      // Ignore — will be removed on next poll anyway
    } finally {
      setQueueMap((prev) => {
        const next = { ...prev };
        delete next[fighter.id];
        return next;
      });
      setLeavingId(null);
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
          {fighterList.length > 0 && (
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

        {showAdoptForm && fighterList.length > 0 && (
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

        {/* Match-found banners */}
        {Object.entries(matchFoundMap).map(([fighterId, found]) => {
          const fighter = fighterList.find((f) => f.id === fighterId);
          return (
            <Link key={fighterId} href={`/arena/${found.matchId}`}>
              <div className="mb-4 rounded-lg border border-neon-orange/40 bg-neon-orange/10 px-4 py-3 transition-all hover:bg-neon-orange/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-orange opacity-75" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-neon-orange" />
                    </span>
                    <span className="font-pixel text-[10px] text-neon-orange">
                      MATCH FOUND{fighter ? ` — ${fighter.name}` : ""}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {found.startsAt && <Countdown targetDate={found.startsAt} />}
                    <span className="font-pixel text-[9px] text-muted-foreground">
                      TAP TO WATCH
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}

        <h2 className="mb-4 font-pixel text-xs text-foreground">YOUR FIGHTERS</h2>

        {loading ? (
          <ArcadeLoader text="LOADING FIGHTERS" />
        ) : fighterList.length === 0 ? (
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
            {fighterList.map((fighter) => (
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
                  <span className="font-pixel text-[10px] uppercase">{fighter.game_id}</span>
                  <span>{fighter.character}</span>
                </div>
                <DivisionBadge division={fighter.division_tier} className="mb-3" />

                <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
                  <div>
                    <div className="font-mono text-neon-orange">{fighter.elo_rating.toFixed(0)}</div>
                    <div className="font-pixel text-[9px] text-muted-foreground">ELO</div>
                  </div>
                  <div>
                    <div className="font-mono text-neon-green">{fighter.wins}</div>
                    <div className="font-pixel text-[9px] text-muted-foreground">WINS</div>
                  </div>
                  <div>
                    <div className="font-mono text-neon-red">{fighter.losses}</div>
                    <div className="font-pixel text-[9px] text-muted-foreground">LOSSES</div>
                  </div>
                </div>

                {matchFoundMap[fighter.id] ? (
                  <Link href={`/arena/${matchFoundMap[fighter.id].matchId}`}>
                    <div className="w-full rounded border border-neon-orange/40 bg-neon-orange/10 px-3 py-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="relative flex h-2 w-2">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-orange opacity-75" />
                            <span className="relative inline-flex h-2 w-2 rounded-full bg-neon-orange" />
                          </span>
                          <span className="font-pixel text-[9px] text-neon-orange">MATCH FOUND</span>
                        </div>
                        {matchFoundMap[fighter.id].startsAt && (
                          <Countdown targetDate={matchFoundMap[fighter.id].startsAt!} />
                        )}
                      </div>
                      <div className="mt-1 text-center font-pixel text-[10px] text-muted-foreground">
                        TAP TO WATCH
                      </div>
                    </div>
                  </Link>
                ) : queueMap[fighter.id]?.error ? (
                  <div className="w-full rounded border border-neon-red/30 bg-neon-red/10 px-3 py-1.5 text-center font-pixel text-[10px] text-neon-red">
                    {queueMap[fighter.id].error}
                  </div>
                ) : queueMap[fighter.id] ? (
                  <div className="w-full space-y-1.5">
                    <div className="flex items-center justify-between rounded border border-neon-green/30 bg-neon-green/10 px-3 py-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="relative flex h-2 w-2">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-green opacity-75" />
                          <span className="relative inline-flex h-2 w-2 rounded-full bg-neon-green" />
                        </span>
                        <span className="font-pixel text-[9px] text-neon-green">SEARCHING</span>
                      </div>
                      <span className="font-mono text-[10px] tabular-nums text-neon-green">
                        {formatElapsed(queueMap[fighter.id].elapsed)}
                      </span>
                    </div>
                    {queueMap[fighter.id].queueSize > 0 && (
                      <div className="text-center font-pixel text-[9px] text-muted-foreground">
                        {queueMap[fighter.id].queueSize} in queue
                      </div>
                    )}
                    <button
                      onClick={(e) => { e.preventDefault(); handleLeaveQueue(fighter); }}
                      disabled={leavingId === fighter.id}
                      className="flex w-full items-center justify-center gap-1 rounded border border-border py-1 font-pixel text-[10px] text-muted-foreground transition-colors hover:border-neon-red/40 hover:text-neon-red"
                    >
                      <X className="h-2.5 w-2.5" />
                      {leavingId === fighter.id ? "LEAVING..." : "LEAVE QUEUE"}
                    </button>
                  </div>
                ) : fighter.status === "ready" && (
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
                )}
              </ArcadeCard>
            ))}
          </StaggeredList>
        )}
      </div>
    </PageTransition>
  );
}
