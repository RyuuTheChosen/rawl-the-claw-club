use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{MatchPool, MatchStatus, MatchWinner};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct ResolveMatch<'info> {
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

pub fn handler(ctx: Context<ResolveMatch>, _match_id: [u8; 32], winner: u8) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    require!(pool.status == MatchStatus::Locked, RawlError::MatchNotLocked);

    let match_winner = match winner {
        0 => MatchWinner::SideA,
        1 => MatchWinner::SideB,
        _ => return Err(RawlError::InvalidSide.into()),
    };

    pool.winner = match_winner;
    pool.status = MatchStatus::Resolved;
    pool.resolve_timestamp = Clock::get()?.unix_timestamp;

    // Derive winning_bet_count on-chain from per-side counts
    pool.winning_bet_count = match match_winner {
        MatchWinner::SideA => pool.side_a_bet_count,
        MatchWinner::SideB => pool.side_b_bet_count,
        MatchWinner::None => 0,
    };

    Ok(())
}
