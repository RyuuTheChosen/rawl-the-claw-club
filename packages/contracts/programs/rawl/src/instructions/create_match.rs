use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{MatchPool, MatchStatus, PlatformConfig};

#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct CreateMatch<'info> {
    #[account(
        init,
        payer = creator,
        space = MatchPool::LEN,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    /// CHECK: Vault PDA for holding SOL bets
    #[account(
        seeds = [VAULT_SEED, &match_id],
        bump,
    )]
    pub vault: UncheckedAccount<'info>,

    #[account(
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(mut)]
    pub creator: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(
    ctx: Context<CreateMatch>,
    match_id: [u8; 32],
    fighter_a: Pubkey,
    fighter_b: Pubkey,
) -> Result<()> {
    require!(!ctx.accounts.platform_config.paused, RawlError::PlatformPaused);

    let pool = &mut ctx.accounts.match_pool;
    pool.match_id = match_id;
    pool.fighter_a = fighter_a;
    pool.fighter_b = fighter_b;
    pool.side_a_total = 0;
    pool.side_b_total = 0;
    pool.side_a_bet_count = 0;
    pool.side_b_bet_count = 0;
    pool.winning_bet_count = 0;
    pool.bet_count = 0;
    pool.status = MatchStatus::Open;
    pool.winner = crate::state::MatchWinner::None;
    pool.oracle = ctx.accounts.platform_config.oracle;
    pool.creator = ctx.accounts.creator.key();
    pool.created_at = Clock::get()?.unix_timestamp;
    pool.lock_timestamp = 0;
    pool.resolve_timestamp = 0;
    pool.cancel_timestamp = 0;
    pool.bump = ctx.bumps.match_pool;
    pool.vault_bump = ctx.bumps.vault;

    Ok(())
}
