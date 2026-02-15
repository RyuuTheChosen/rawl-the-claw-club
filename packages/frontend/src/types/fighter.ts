export interface Fighter {
  id: string;
  name: string;
  game_id: string;
  character: string;
  elo_rating: number;
  matches_played: number;
  wins: number;
  losses: number;
  status: "validating" | "calibrating" | "ready" | "rejected" | "suspended";
  division_tier: "Bronze" | "Silver" | "Gold" | "Diamond";
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  fighter_id: string;
  fighter_name: string;
  owner_wallet: string;
  elo_rating: number;
  wins: number;
  losses: number;
  matches_played: number;
  division: "Bronze" | "Silver" | "Gold" | "Diamond";
}
