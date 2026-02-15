use anchor_lang::prelude::*;

use super::match_pool::MatchWinner;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum BetSide {
    SideA,
    SideB,
}

#[account]
pub struct Bet {
    pub bettor: Pubkey,
    pub match_id: [u8; 32],
    pub side: BetSide,
    pub amount: u64,
    pub claimed: bool,
    pub bump: u8,
}

impl Bet {
    pub const LEN: usize = 8   // discriminator
        + 32   // bettor
        + 32   // match_id
        + 1    // side
        + 8    // amount
        + 1    // claimed
        + 1;   // bump

    pub fn is_winner(&self, match_winner: MatchWinner) -> bool {
        match (self.side, match_winner) {
            (BetSide::SideA, MatchWinner::SideA) => true,
            (BetSide::SideB, MatchWinner::SideB) => true,
            _ => false,
        }
    }
}
