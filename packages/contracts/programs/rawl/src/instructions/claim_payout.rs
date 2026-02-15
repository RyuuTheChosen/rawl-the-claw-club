use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, MatchPool, MatchStatus, PlatformConfig};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct ClaimPayout<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        mut,
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

    #[account(
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(mut)]
    pub bettor: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<ClaimPayout>, match_id: [u8; 32]) -> Result<()> {
    let pool = &ctx.accounts.match_pool;
    let bet = &mut ctx.accounts.bet;

    require!(pool.status == MatchStatus::Resolved, RawlError::MatchNotResolved);
    require!(!bet.claimed, RawlError::AlreadyClaimed);
    require!(bet.is_winner(pool.winner), RawlError::BetOnLosingSide);

    // Calculate payout with u128 intermediate math
    let total_pool = (pool.side_a_total as u128)
        .checked_add(pool.side_b_total as u128)
        .ok_or(RawlError::Overflow)?;

    let fee = total_pool
        .checked_mul(ctx.accounts.platform_config.fee_bps as u128)
        .ok_or(RawlError::Overflow)?
        .checked_div(10_000)
        .ok_or(RawlError::Overflow)?;

    let net_pool = total_pool.checked_sub(fee).ok_or(RawlError::Overflow)?;

    let winning_side_total = match pool.winner {
        crate::state::MatchWinner::SideA => pool.side_a_total as u128,
        crate::state::MatchWinner::SideB => pool.side_b_total as u128,
        _ => return Err(RawlError::InvalidMatchStatus.into()),
    };

    let payout = net_pool
        .checked_mul(bet.amount as u128)
        .ok_or(RawlError::Overflow)?
        .checked_div(winning_side_total)
        .ok_or(RawlError::Overflow)? as u64;

    // Transfer from vault to bettor
    let vault_info = ctx.accounts.vault.to_account_info();
    let bettor_info = ctx.accounts.bettor.to_account_info();
    **vault_info.try_borrow_mut_lamports()? -= payout;
    **bettor_info.try_borrow_mut_lamports()? += payout;

    bet.claimed = true;

    // Decrement winning_bet_count
    let pool = &mut ctx.accounts.match_pool;
    pool.winning_bet_count = pool.winning_bet_count.saturating_sub(1);

    Ok(())
}
