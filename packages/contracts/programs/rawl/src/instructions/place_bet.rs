use anchor_lang::prelude::*;
use anchor_lang::system_program;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{Bet, BetSide, MatchPool, MatchStatus};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32], side: u8)]
pub struct PlaceBet<'info> {
    #[account(
        mut,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    #[account(
        init,
        payer = bettor,
        space = Bet::LEN,
        seeds = [BET_SEED, &match_id, bettor.key().as_ref()],
        bump,
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

pub fn handler(ctx: Context<PlaceBet>, match_id: [u8; 32], side: u8, amount: u64) -> Result<()> {
    require!(amount > 0, RawlError::ZeroBetAmount);
    require!(
        ctx.accounts.match_pool.status == MatchStatus::Open,
        RawlError::MatchNotOpen
    );

    // Enforce minimum bet amount
    let min_bet = ctx.accounts.match_pool.min_bet;
    if min_bet > 0 {
        require!(amount >= min_bet, RawlError::BetBelowMinimum);
    }

    // Enforce betting window
    let betting_window = ctx.accounts.match_pool.betting_window;
    if betting_window > 0 {
        let clock = Clock::get()?;
        let deadline = ctx.accounts.match_pool.created_at
            .checked_add(betting_window)
            .ok_or(RawlError::Overflow)?;
        require!(clock.unix_timestamp <= deadline, RawlError::BettingWindowClosed);
    }

    let bet_side = match side {
        0 => BetSide::SideA,
        1 => BetSide::SideB,
        _ => return Err(RawlError::InvalidSide.into()),
    };

    // Transfer SOL to vault
    system_program::transfer(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.bettor.to_account_info(),
                to: ctx.accounts.vault.to_account_info(),
            },
        ),
        amount,
    )?;

    // Update match pool
    let pool = &mut ctx.accounts.match_pool;
    match bet_side {
        BetSide::SideA => {
            pool.side_a_total = pool.side_a_total.checked_add(amount).ok_or(RawlError::Overflow)?;
            pool.side_a_bet_count = pool.side_a_bet_count.checked_add(1).ok_or(RawlError::Overflow)?;
        }
        BetSide::SideB => {
            pool.side_b_total = pool.side_b_total.checked_add(amount).ok_or(RawlError::Overflow)?;
            pool.side_b_bet_count = pool.side_b_bet_count.checked_add(1).ok_or(RawlError::Overflow)?;
        }
    }
    pool.bet_count = pool.bet_count.checked_add(1).ok_or(RawlError::Overflow)?;

    // Initialize bet PDA
    let bet = &mut ctx.accounts.bet;
    bet.bettor = ctx.accounts.bettor.key();
    bet.match_id = match_id;
    bet.side = bet_side;
    bet.amount = amount;
    bet.claimed = false;
    bet.bump = ctx.bumps.bet;

    Ok(())
}
