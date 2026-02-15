use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, MatchPool, MatchStatus, PlatformConfig};

/// Sweep abandoned bet on cancelled match — returns wager to bettor (not treasury)
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct SweepCancelled<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        mut,
        close = bettor_dest,
        seeds = [BET_SEED, &match_id, bet.bettor.as_ref()],
        bump = bet.bump,
    )]
    pub bet: Account<'info, Bet>,

    /// CHECK: Vault PDA
    #[account(
        mut,
        seeds = [VAULT_SEED, &match_id],
        bump = match_pool.vault_bump,
    )]
    pub vault: UncheckedAccount<'info>,

    #[account(
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    /// CHECK: Original bettor's wallet — receives the refund
    #[account(mut, constraint = bettor_dest.key() == bet.bettor)]
    pub bettor_dest: UncheckedAccount<'info>,

    pub caller: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<SweepCancelled>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let bet = &ctx.accounts.bet;

    require!(pool.status == MatchStatus::Cancelled, RawlError::MatchNotCancelled);

    // 30-day window must have elapsed since cancellation
    let now = Clock::get()?.unix_timestamp;
    let elapsed = now.saturating_sub(pool.cancel_timestamp);
    require!(elapsed >= CLAIM_WINDOW_SECONDS, RawlError::ClaimWindowNotElapsed);

    // Return wager to bettor (NOT treasury)
    let vault_info = ctx.accounts.vault.to_account_info();
    let bettor_info = ctx.accounts.bettor_dest.to_account_info();
    let transfer_amount = bet.amount.min(vault_info.lamports());

    if transfer_amount > 0 {
        **vault_info.try_borrow_mut_lamports()? -= transfer_amount;
        **bettor_info.try_borrow_mut_lamports()? += transfer_amount;
    }

    // Decrement bet_count
    pool.bet_count = pool.bet_count.saturating_sub(1);

    Ok(())
}
