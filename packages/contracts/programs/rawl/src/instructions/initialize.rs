use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::state::PlatformConfig;

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = PlatformConfig::LEN,
        seeds = [PLATFORM_CONFIG_SEED],
        bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(mut)]
    pub authority: Signer<'info>,

    /// CHECK: Oracle public key, validated by the authority
    pub oracle: UncheckedAccount<'info>,

    /// CHECK: Treasury account for fee collection
    pub treasury: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<Initialize>, fee_bps: u16, match_timeout: i64) -> Result<()> {
    require!(fee_bps <= MAX_FEE_BPS, RawlError::InvalidFeeBps);

    let config = &mut ctx.accounts.platform_config;
    config.authority = ctx.accounts.authority.key();
    config.oracle = ctx.accounts.oracle.key();
    config.fee_bps = fee_bps;
    config.treasury = ctx.accounts.treasury.key();
    config.paused = false;
    config.match_timeout = match_timeout;
    config.bump = ctx.bumps.platform_config;

    Ok(())
}
