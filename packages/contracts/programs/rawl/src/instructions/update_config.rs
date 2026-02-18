use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::RawlError;
use crate::events::ConfigUpdated;
use crate::state::PlatformConfig;

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(
        mut,
        seeds = [PLATFORM_CONFIG_SEED],
        bump = platform_config.bump,
    )]
    pub platform_config: Account<'info, PlatformConfig>,

    #[account(
        constraint = authority.key() == platform_config.authority @ RawlError::Unauthorized,
    )]
    pub authority: Signer<'info>,
}

pub fn handler(
    ctx: Context<UpdateConfig>,
    fee_bps: Option<u16>,
    match_timeout: Option<i64>,
    paused: Option<bool>,
    oracle: Option<Pubkey>,
    treasury: Option<Pubkey>,
) -> Result<()> {
    let config = &mut ctx.accounts.platform_config;

    if let Some(fee_bps) = fee_bps {
        require!(fee_bps <= MAX_FEE_BPS, RawlError::InvalidFeeBps);
        config.fee_bps = fee_bps;
        emit!(ConfigUpdated {
            field: "fee_bps".to_string(),
            value: fee_bps as u64,
        });
    }

    if let Some(match_timeout) = match_timeout {
        require!(match_timeout > 0, RawlError::InvalidTimeout);
        config.match_timeout = match_timeout;
        emit!(ConfigUpdated {
            field: "match_timeout".to_string(),
            value: match_timeout as u64,
        });
    }

    if let Some(paused) = paused {
        config.paused = paused;
        emit!(ConfigUpdated {
            field: "paused".to_string(),
            value: paused as u64,
        });
    }

    if let Some(oracle) = oracle {
        config.oracle = oracle;
        emit!(ConfigUpdated {
            field: "oracle".to_string(),
            value: 0,
        });
    }

    if let Some(treasury) = treasury {
        config.treasury = treasury;
        emit!(ConfigUpdated {
            field: "treasury".to_string(),
            value: 0,
        });
    }

    Ok(())
}
