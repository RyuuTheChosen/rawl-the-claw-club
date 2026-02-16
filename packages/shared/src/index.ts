// Shared types between frontend and contracts

export type MatchStatus = "open" | "locked" | "resolved" | "cancelled";
export type MatchType = "ranked" | "challenge" | "exhibition";
export type FighterStatus = "validating" | "calibrating" | "ready" | "rejected" | "suspended";
export type Division = "Bronze" | "Silver" | "Gold" | "Diamond";
export type BetSide = "a" | "b";

export const GAMES = ["sfiii3n", "kof98", "tektagt", "umk3", "doapp"] as const;
export type GameId = (typeof GAMES)[number];

export const DIVISION_THRESHOLDS: Record<Division, number> = {
  Diamond: 1600,
  Gold: 1400,
  Silver: 1200,
  Bronze: 0,
};

export const PLATFORM_FEE_BPS = 300; // 3%
export const MATCH_TIMEOUT_SECONDS = 1800; // 30 minutes
export const CLAIM_WINDOW_DAYS = 30;

export const MATCH_FORMATS = [1, 3, 5] as const;
export type MatchFormat = (typeof MATCH_FORMATS)[number];

export const TRAINING_TIERS = ["free", "standard", "pro"] as const;
export type TrainingTier = (typeof TRAINING_TIERS)[number];
