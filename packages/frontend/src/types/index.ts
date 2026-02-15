export type { Match, MatchDataMessage } from "./match";
export type { Fighter, LeaderboardEntry } from "./fighter";

export interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}
