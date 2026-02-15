use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::{MatchPool, PlatformConfig};

/// Close MatchPool + Vault PDAs when bet_count == 0
#[derive(Accounts)]
#[instruction(match_id: [u8; 32])]
pub struct CloseMatch<'info> {
    #[account(
        mut,
        close = authority,
        seeds = [MATCH_POOL_SEED, &match_id],
        bump = match_pool.bump,
    )]
    pub match_pool: Account<'info, MatchPool>,

    /// CHECK: Vault PDA — lamports returned to authority
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

    #[account(
        mut,
        constraint = authority.key() == platform_config.authority @ RawlError::Unauthorized,
    )]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<CloseMatch>, _match_id: [u8; 32]) -> Result<()> {
    let pool = &ctx.accounts.match_pool;
    require!(pool.bet_count == 0, RawlError::BetCountNotZero);

    // Transfer any remaining vault lamports to authority
    let vault_info = ctx.accounts.vault.to_account_info();
    let authority_info = ctx.accounts.authority.to_account_info();
    let vault_lamports = vault_info.lamports();
    if vault_lamports > 0 {
        **vault_info.try_borrow_mut_lamports()? -= vault_lamports;
        **authority_info.try_borrow_mut_lamports()? += vault_lamports;
    }

    // MatchPool close handled by anchor `close` attribute
    Ok(())
}
