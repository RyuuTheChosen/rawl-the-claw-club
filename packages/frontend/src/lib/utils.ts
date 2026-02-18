import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { Match, MatchDataMessage } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export type WinnerInfo = {
  name: string;
  side: "a" | "b";
} | null;

/**
 * Derive winner from WS live data (priority) or REST match object (fallback).
 * Returns null when match is not resolved or winner cannot be determined.
 */
export function getWinnerInfo(
  match: Match,
  wsData?: MatchDataMessage | null,
): WinnerInfo {
  const nameA = match.fighter_a_name ?? match.fighter_a_id.slice(0, 8);
  const nameB = match.fighter_b_name ?? match.fighter_b_id.slice(0, 8);

  // WS fires before the REST poll updates — prefer it
  if (wsData?.match_winner === 1) return { name: nameA, side: "a" };
  if (wsData?.match_winner === 2) return { name: nameB, side: "b" };

  // REST fallback — only trust when status is actually "resolved"
  if (match.status === "resolved" && match.winner_id) {
    if (match.winner_id === match.fighter_a_id) return { name: nameA, side: "a" };
    if (match.winner_id === match.fighter_b_id) return { name: nameB, side: "b" };
  }

  return null;
}
