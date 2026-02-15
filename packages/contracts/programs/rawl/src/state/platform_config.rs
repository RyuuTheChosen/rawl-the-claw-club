use anchor_lang::prelude::*;

#[account]
#[derive(Default)]
pub struct PlatformConfig {
    pub authority: Pubkey,
    pub oracle: Pubkey,
    pub fee_bps: u16,
    pub treasury: Pubkey,
    pub paused: bool,
    pub match_timeout: i64,
    pub bump: u8,
}

impl PlatformConfig {
    pub const LEN: usize = 8  // discriminator
        + 32  // authority
        + 32  // oracle
        + 2   // fee_bps
        + 32  // treasury
        + 1   // paused
        + 8   // match_timeout
        + 1;  // bump
}
