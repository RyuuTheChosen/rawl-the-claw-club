use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, MatchPool, MatchStatus, PlatformConfig};

/// Sweep unclaimed winning bet to treasury after 30 days, decrement winning_bet_count
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct SweepUnclaimed<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        mut,
        close = treasury,
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

    /// CHECK: Treasury
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

pub fn handler(ctx: Context<SweepUnclaimed>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &mut ctx.accounts.match_pool;
    let bet = &ctx.accounts.bet;

    require!(pool.status == MatchStatus::Resolved, RawlError::MatchNotResolved);
    require!(!bet.claimed, RawlError::AlreadyClaimed);
    require!(bet.is_winner(pool.winner), RawlError::BetOnLosingSide);

    // Claim window must have elapsed
    let now = Clock::get()?.unix_timestamp;
    let elapsed = now.saturating_sub(pool.resolve_timestamp);
    require!(elapsed >= CLAIM_WINDOW_SECONDS, RawlError::ClaimWindowNotElapsed);

    // Calculate unclaimed payout using snapshotted fee_bps
    let total_pool = (pool.side_a_total as u128)
        .checked_add(pool.side_b_total as u128)
        .ok_or(RawlError::Overflow)?;

    let fee = total_pool
        .checked_mul(pool.fee_bps as u128)
        .ok_or(RawlError::Overflow)?
        .checked_div(10_000)
        .ok_or(RawlError::Overflow)?;

    let net_pool = total_pool.checked_sub(fee).ok_or(RawlError::Overflow)?;

    let winning_side_total = match pool.winner {
        crate::state::MatchWinner::SideA => pool.side_a_total as u128,
        crate::state::MatchWinner::SideB => pool.side_b_total as u128,
        _ => return Err(RawlError::InvalidMatchStatus.into()),
    };

    let payout = u64::try_from(
        net_pool
            .checked_mul(bet.amount as u128)
            .ok_or(RawlError::Overflow)?
            .checked_div(winning_side_total)
            .ok_or(RawlError::Overflow)?
    ).map_err(|_| RawlError::Overflow)?;

    // Transfer unclaimed winnings from vault to treasury
    let vault_info = ctx.accounts.vault.to_account_info();
    require!(vault_info.lamports() >= payout, RawlError::InsufficientVault);
    let treasury_info = ctx.accounts.treasury.to_account_info();
    let transfer_amount = payout;

    if transfer_amount > 0 {
        **vault_info.try_borrow_mut_lamports()? -= transfer_amount;
        **treasury_info.try_borrow_mut_lamports()? += transfer_amount;
    }

    // Decrement winning_bet_count and bet_count
    pool.winning_bet_count = pool.winning_bet_count.saturating_sub(1);
    pool.bet_count = pool.bet_count.saturating_sub(1);

    Ok(())
}
