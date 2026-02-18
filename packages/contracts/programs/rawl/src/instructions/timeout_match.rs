use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::MatchCancelled;
use crate::state::{MatchPool, MatchStatus, PlatformConfig};

/// Permissionless — anyone can call this after 30-minute timeout
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct TimeoutMatch<'info> {
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

    pub caller: Signer<'info>,
}

pub fn handler(ctx: Context<TimeoutMatch>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let config = &ctx.accounts.platform_config;

    require!(pool.status == MatchStatus::Locked, RawlError::MatchNotLocked);

    let now = Clock::get()?.unix_timestamp;
    let elapsed = now.saturating_sub(pool.lock_timestamp);
    require!(elapsed > config.match_timeout, RawlError::TimeoutNotElapsed);

    pool.status = MatchStatus::Cancelled;
    pool.cancel_timestamp = now;

    emit!(MatchCancelled {
        match_id: pool.match_id,
    });

    Ok(())
}
