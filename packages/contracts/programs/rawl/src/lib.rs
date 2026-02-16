use anchor_lang::prelude::*;

pub mod constants;
pub mod errors;
pub mod instructions;
pub mod state;

use instructions::*;

declare_id!("AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K");

#[program]
pub mod rawl {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, fee_bps: u16, match_timeout: i64) -> Result<()> {
        instructions::initialize::handler(ctx, fee_bps, match_timeout)
    }

    pub fn create_match(
        ctx: Context<CreateMatch>,
        match_id: [u8; 32],
        fighter_a: Pubkey,
        fighter_b: Pubkey,
    ) -> Result<()> {
        instructions::create_match::handler(ctx, match_id, fighter_a, fighter_b)
    }

    pub fn place_bet(
        ctx: Context<PlaceBet>,
        match_id: [u8; 32],
        side: u8,
        amount: u64,
    ) -> Result<()> {
        instructions::place_bet::handler(ctx, match_id, side, amount)
    }

    pub fn lock_match(ctx: Context<LockMatch>, match_id: [u8; 32]) -> Result<()> {
        instructions::lock_match::handler(ctx, match_id)
    }

    pub fn resolve_match(
        ctx: Context<ResolveMatch>,
        match_id: [u8; 32],
        winner: u8,
    ) -> Result<()> {
        instructions::resolve_match::handler(ctx, match_id, winner)
    }

    pub fn claim_payout(ctx: Context<ClaimPayout>, match_id: [u8; 32]) -> Result<()> {
        instructions::claim_payout::handler(ctx, match_id)
    }

    pub fn cancel_match(ctx: Context<CancelMatch>, match_id: [u8; 32]) -> Result<()> {
        instructions::cancel_match::handler(ctx, match_id)
    }

    pub fn timeout_match(ctx: Context<TimeoutMatch>, match_id: [u8; 32]) -> Result<()> {
        instructions::timeout_match::handler(ctx, match_id)
    }

    pub fn refund_bet(ctx: Context<RefundBet>, match_id: [u8; 32]) -> Result<()> {
        instructions::refund_bet::handler(ctx, match_id)
    }

    pub fn close_bet(ctx: Context<CloseBet>, match_id: [u8; 32]) -> Result<()> {
        instructions::close_bet::handler(ctx, match_id)
    }

    pub fn close_match(ctx: Context<CloseMatch>, match_id: [u8; 32]) -> Result<()> {
        instructions::close_match::handler(ctx, match_id)
    }

    pub fn withdraw_fees(ctx: Context<WithdrawFees>, match_id: [u8; 32]) -> Result<()> {
        instructions::withdraw_fees::handler(ctx, match_id)
    }

    pub fn sweep_unclaimed(ctx: Context<SweepUnclaimed>, match_id: [u8; 32]) -> Result<()> {
        instructions::sweep_unclaimed::handler(ctx, match_id)
    }

    pub fn sweep_cancelled(ctx: Context<SweepCancelled>, match_id: [u8; 32]) -> Result<()> {
        instructions::sweep_cancelled::handler(ctx, match_id)
    }

    pub fn update_authority(ctx: Context<UpdateAuthority>) -> Result<()> {
        instructions::update_authority::handler(ctx)
    }
}
