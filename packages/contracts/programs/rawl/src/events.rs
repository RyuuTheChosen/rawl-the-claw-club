use anchor_lang::prelude::*;

#[event]
pub struct MatchCreated {
    pub match_id: [u8; 32],
    pub fighter_a: Pubkey,
    pub fighter_b: Pubkey,
}

#[event]
pub struct BetPlaced {
    pub match_id: [u8; 32],
    pub bettor: Pubkey,
    pub side: u8,
    pub amount: u64,
}

#[event]
pub struct MatchLocked {
    pub match_id: [u8; 32],
}

#[event]
pub struct MatchResolved {
    pub match_id: [u8; 32],
    pub winner: u8,
}

#[event]
pub struct PayoutClaimed {
    pub match_id: [u8; 32],
    pub bettor: Pubkey,
    pub amount: u64,
}

#[event]
pub struct MatchCancelled {
    pub match_id: [u8; 32],
}

#[event]
pub struct BetRefunded {
    pub match_id: [u8; 32],
    pub bettor: Pubkey,
    pub amount: u64,
}

#[event]
pub struct FeesWithdrawn {
    pub match_id: [u8; 32],
    pub amount: u64,
}

#[event]
pub struct ConfigUpdated {
    pub field: String,
    pub value: u64,
}
