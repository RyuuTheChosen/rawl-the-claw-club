export type { Match, MatchDataMessage } from "./match";
export type { Fighter, LeaderboardEntry } from "./fighter";

export interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

// Inlined from @rawl/shared to avoid monorepo cross-package dependency issues on Vercel
export type MatchStatus = "open" | "locked" | "resolved" | "cancelled";
export type MatchType = "ranked" | "challenge" | "exhibition";
export type FighterStatus = "validating" | "calibrating" | "ready" | "rejected" | "suspended";
export type Division = "Bronze" | "Silver" | "Gold" | "Diamond";
export type BetSide = "a" | "b";
export type GameId = "sf2ce" | "sfiii3n" | "kof98" | "tektagt" | "umk3" | "doapp";
export type MatchFormat = 1 | 3 | 5;
export const PLATFORM_FEE_BPS = 300;
export const MATCH_TIMEOUT_SECONDS = 1800;
export const CLAIM_WINDOW_DAYS = 30;

export interface PretrainedModel {
  id: string;
  game_id: string;
  name: string;
  character: string;
  description: string;
}

export type BetStatus = "pending" | "confirmed" | "claimed" | "refunded" | "expired";

export interface Bet {
  id: string;
  match_id: string;
  wallet_address: string;
  side: BetSide;
  amount_eth: number;
  onchain_bet_id: string | null;
  status: BetStatus;
  created_at: string;
  claimed_at: string | null;
  game_id: string;
  fighter_a_name: string | null;
  fighter_b_name: string | null;
  match_status: string;
  match_winner_id: string | null;
  winner_side: "a" | "b" | null;
}
