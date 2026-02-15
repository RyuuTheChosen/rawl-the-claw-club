use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum MatchStatus {
    Open,
    Locked,
    Resolved,
    Cancelled,
}

impl Default for MatchStatus {
    fn default() -> Self {
        MatchStatus::Open
    }
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum MatchWinner {
    None,
    SideA,
    SideB,
}

impl Default for MatchWinner {
    fn default() -> Self {
        MatchWinner::None
    }
}

#[account]
#[derive(Default)]
pub struct MatchPool {
    pub match_id: [u8; 32],
    pub fighter_a: Pubkey,
    pub fighter_b: Pubkey,
    pub side_a_total: u64,
    pub side_b_total: u64,
    pub side_a_bet_count: u32,
    pub side_b_bet_count: u32,
    pub winning_bet_count: u32,
    pub bet_count: u32,
    pub status: MatchStatus,
    pub winner: MatchWinner,
    pub oracle: Pubkey,
    pub creator: Pubkey,
    pub created_at: i64,
    pub lock_timestamp: i64,
    pub resolve_timestamp: i64,
    pub cancel_timestamp: i64,
    pub min_bet: u64,
    pub betting_window: i64,
    pub bump: u8,
    pub vault_bump: u8,
}

impl MatchPool {
    pub const LEN: usize = 8   // discriminator
        + 32   // match_id
        + 32   // fighter_a
        + 32   // fighter_b
        + 8    // side_a_total
        + 8    // side_b_total
        + 4    // side_a_bet_count
        + 4    // side_b_bet_count
        + 4    // winning_bet_count
        + 4    // bet_count
        + 1    // status
        + 1    // winner
        + 32   // oracle
        + 32   // creator
        + 8    // created_at
        + 8    // lock_timestamp
        + 8    // resolve_timestamp
        + 8    // cancel_timestamp
        + 8    // min_bet
        + 8    // betting_window
        + 1    // bump
        + 1;   // vault_bump
}
