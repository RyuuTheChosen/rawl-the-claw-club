use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::FeesWithdrawn;
use crate::state::{MatchPool, MatchStatus, PlatformConfig};

/// Withdraw platform fees after 30-day claim window + winning_bet_count == 0
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct WithdrawFees<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

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

    /// CHECK: Treasury account
    #[account(
        mut,
        constraint = treasury.key() == platform_config.treasury,
    )]
    pub treasury: UncheckedAccount<'info>,

    #[account(
        constraint = authority.key() == platform_config.authority @ RawlError::Unauthorized,
    )]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<WithdrawFees>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;

    require!(pool.status == MatchStatus::Resolved, RawlError::MatchNotResolved);
    require!(!pool.fees_withdrawn, RawlError::FeesAlreadyWithdrawn);
    require!(pool.winning_bet_count == 0, RawlError::WinningBetCountNotZero);

    // Time gate: 30-day claim window must have elapsed
    let now = Clock::get()?.unix_timestamp;
    let elapsed = now.saturating_sub(pool.resolve_timestamp);
    require!(elapsed >= CLAIM_WINDOW_SECONDS, RawlError::ClaimWindowNotElapsed);

    // Calculate fee amount using snapshotted fee_bps
    let total_pool = (pool.side_a_total as u128)
        .checked_add(pool.side_b_total as u128)
        .ok_or(RawlError::Overflow)?;

    let fee = u64::try_from(
        total_pool
            .checked_mul(pool.fee_bps as u128)
            .ok_or(RawlError::Overflow)?
            .checked_div(10_000)
            .ok_or(RawlError::Overflow)?
    ).map_err(|_| RawlError::Overflow)?;

    // Transfer fee from vault to treasury
    let vault_info = ctx.accounts.vault.to_account_info();
    let treasury_info = ctx.accounts.treasury.to_account_info();

    let available = vault_info.lamports();
    let transfer_amount = fee.min(available);

    if transfer_amount > 0 {
        **vault_info.try_borrow_mut_lamports()? -= transfer_amount;
        **treasury_info.try_borrow_mut_lamports()? += transfer_amount;
    }

    pool.fees_withdrawn = true;

    emit!(FeesWithdrawn {
        match_id: pool.match_id,
        amount: transfer_amount,
    });

    Ok(())
}
