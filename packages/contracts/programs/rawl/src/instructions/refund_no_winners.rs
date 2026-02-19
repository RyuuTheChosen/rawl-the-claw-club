use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::BetRefunded;
use crate::state::{Bet, MatchPool, MatchStatus};

/// Refund losing bettors when a match resolves but the winning side has zero bets.
/// Standard parimutuel edge case: no winners to distribute to, so losers reclaim
/// their wagers minus the platform fee.
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct RefundNoWinners<'info> {
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

pub fn handler(ctx: Context<RefundNoWinners>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let bet = &ctx.accounts.bet;

    require!(pool.status == MatchStatus::Resolved, RawlError::MatchNotResolved);
    require!(pool.winning_bet_count == 0, RawlError::WinnersExist);

    // Refund = bet.amount minus proportional platform fee
    // Uses u128 intermediate to avoid overflow
    let fee_bps = pool.fee_bps as u128;
    let refund_amount = u64::try_from(
        (bet.amount as u128)
            .checked_mul(
                10_000u128.checked_sub(fee_bps).ok_or(RawlError::Overflow)?
            )
            .ok_or(RawlError::Overflow)?
            .checked_div(10_000)
            .ok_or(RawlError::Overflow)?
    ).map_err(|_| RawlError::Overflow)?;

    // Vault balance check
    let vault_info = ctx.accounts.vault.to_account_info();
    require!(vault_info.lamports() >= refund_amount, RawlError::InsufficientVault);

    // Transfer refund from vault to bettor
    let bettor_info = ctx.accounts.bettor.to_account_info();
    **vault_info.try_borrow_mut_lamports()? -= refund_amount;
    **bettor_info.try_borrow_mut_lamports()? += refund_amount;

    emit!(BetRefunded {
        match_id: pool.match_id,
        bettor: ctx.accounts.bettor.key(),
        amount: refund_amount,
    });

    // Decrement bet_count (PDA close handled by Anchor `close` attribute)
    pool.bet_count = pool.bet_count.saturating_sub(1);

    Ok(())
}
