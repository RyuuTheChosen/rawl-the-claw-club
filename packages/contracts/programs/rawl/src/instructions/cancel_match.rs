use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::MatchCancelled;
use crate::state::{MatchPool, MatchStatus, PlatformConfig};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct CancelMatch<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(
        constraint = authority.key() == platform_config.authority @ RawlError::Unauthorized,
    )]
    pub authority: Signer<'info>,
}

pub fn handler(ctx: Context<CancelMatch>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;

    require!(
        pool.status == MatchStatus::Open || pool.status == MatchStatus::Locked,
        RawlError::InvalidMatchStatus
    );

    pool.status = MatchStatus::Cancelled;
    pool.cancel_timestamp = Clock::get()?.unix_timestamp;

    emit!(MatchCancelled {
        match_id: pool.match_id,
    });

    Ok(())
}
