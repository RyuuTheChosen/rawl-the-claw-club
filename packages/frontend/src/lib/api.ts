import type { Match, Fighter, PaginatedResponse, LeaderboardEntry, PretrainedModel } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getMatches(params?: {
  cursor?: string;
  limit?: number;
  status?: string;
  game?: string;
  fighter_id?: string;
}): Promise<PaginatedResponse<Match>> {
  const searchParams = new URLSearchParams();
  if (params?.cursor) searchParams.set("cursor", params.cursor);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.game) searchParams.set("game", params.game);
  if (params?.fighter_id) searchParams.set("fighter_id", params.fighter_id);
  const qs = searchParams.toString();
  return fetchJson(`/matches${qs ? `?${qs}` : ""}`);
}

export async function getMatch(id: string): Promise<Match> {
  return fetchJson(`/matches/${id}`);
}

export async function getFighters(game?: string): Promise<PaginatedResponse<Fighter>> {
  const qs = game ? `?game=${game}` : "";
  return fetchJson(`/fighters${qs}`);
}

export async function getFighter(id: string): Promise<Fighter> {
  return fetchJson(`/fighters/${id}`);
}

export async function getOdds(matchId: string) {
  return fetchJson(`/odds/${matchId}`);
}

export async function getLeaderboard(
  gameId: string,
  limit = 50
): Promise<LeaderboardEntry[]> {
  return fetchJson(`/leaderboard/${gameId}?limit=${limit}`);
}

export async function getPretrainedModels(): Promise<PretrainedModel[]> {
  return fetchJson("/pretrained");
}
