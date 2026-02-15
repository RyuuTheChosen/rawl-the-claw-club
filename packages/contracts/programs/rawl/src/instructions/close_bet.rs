use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, MatchPool, MatchStatus};

/// Close a bet PDA on a resolved match (claimed winners or losing bets)
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct CloseBet<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        mut,
        close = bettor,
        seeds = [BET_SEED, &match_id, bettor.key().as_ref()],
        bump = bet.bump,
        constraint = bet.bettor == bettor.key(),
    )]
    pub bet: Account<'info, Bet>,

    #[account(mut)]
    pub bettor: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<CloseBet>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let bet = &ctx.accounts.bet;

    require!(pool.status == MatchStatus::Resolved, RawlError::MatchNotResolved);

    // Can only close if already claimed (winner) or on the losing side
    if bet.is_winner(pool.winner) {
        require!(bet.claimed, RawlError::AlreadyClaimed);
    }

    // Decrement bet_count
    pool.bet_count = pool.bet_count.saturating_sub(1);

    Ok(())
}
