export interface Match {
  id: string;
  game_id: string;
  match_format: number;
  fighter_a_id: string;
  fighter_b_id: string;
  fighter_a_name: string | null;
  fighter_b_name: string | null;
  winner_id: string | null;
  status: "open" | "locked" | "resolved" | "cancelled";
  match_type: "ranked" | "challenge" | "exhibition";
  has_pool: boolean;
  side_a_total: number;
  side_b_total: number;
  created_at: string;
  starts_at: string | null;
  locked_at: string | null;
  resolved_at: string | null;
  replay_s3_key: string | null;
}

export interface MatchDataMessage {
  match_id: string;
  timestamp: string;
  health_a: number;
  health_b: number;
  round: number;
  timer: number;
  status: string;
  round_winner: number | null;
  match_winner: number | null;
  team_health_a: number[] | null;
  team_health_b: number[] | null;
  active_char_a: number | null;
  active_char_b: number | null;
  odds_a: number;
  odds_b: number;
  pool_total: number;
}
