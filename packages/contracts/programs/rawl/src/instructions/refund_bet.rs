use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, MatchPool, MatchStatus};

/// Atomic refund + PDA close (single tx) for cancelled matches
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct RefundBet<'info> {
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

    /// CHECK: Vault PDA
    #[account(
        mut,
        seeds = [VAULT_SEED, &match_id],
        bump = match_pool.vault_bump,
    )]
    pub vault: UncheckedAccount<'info>,

    #[account(mut)]
    pub bettor: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<RefundBet>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let bet = &ctx.accounts.bet;

    require!(pool.status == MatchStatus::Cancelled, RawlError::MatchNotCancelled);

    // Transfer wager back from vault to bettor
    let vault_info = ctx.accounts.vault.to_account_info();
    let bettor_info = ctx.accounts.bettor.to_account_info();
    **vault_info.try_borrow_mut_lamports()? -= bet.amount;
    **bettor_info.try_borrow_mut_lamports()? += bet.amount;

    // Decrement bet_count (PDA close handled by anchor `close` attribute)
    pool.bet_count = pool.bet_count.saturating_sub(1);

    Ok(())
}
