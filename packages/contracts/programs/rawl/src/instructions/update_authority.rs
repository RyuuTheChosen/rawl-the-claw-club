use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::PlatformConfig;

/// Key rotation for platform authority
#[derive(Accounts)]
pub struct UpdateAuthority<'info> {
    #[account(
        mut,
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(
        constraint = current_authority.key() == platform_config.authority @ RawlError::Unauthorized,
    )]
    pub current_authority: Signer<'info>,

    /// CHECK: New authority pubkey
    pub new_authority: UncheckedAccount<'info>,
}

pub fn handler(ctx: Context<UpdateAuthority>) -> Result<()> {
    let config = &mut ctx.accounts.platform_config;
    config.authority = ctx.accounts.new_authority.key();
    Ok(())
}
