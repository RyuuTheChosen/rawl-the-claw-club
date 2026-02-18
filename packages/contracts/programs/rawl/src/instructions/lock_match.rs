use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::MatchLocked;
use crate::state::{MatchPool, MatchStatus};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct LockMatch<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        constraint = oracle.key() == match_pool.oracle @ RawlError::OracleUnauthorized,
    )]
    pub oracle: Signer<'info>,
}

pub fn handler(ctx: Context<LockMatch>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    require!(pool.status == MatchStatus::Open, RawlError::MatchNotOpen);

    pool.status = MatchStatus::Locked;
    pool.lock_timestamp = Clock::get()?.unix_timestamp;

    emit!(MatchLocked {
        match_id: pool.match_id,
    });

    Ok(())
}
