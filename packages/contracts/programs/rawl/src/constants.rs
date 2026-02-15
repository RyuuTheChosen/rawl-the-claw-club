use anchor_lang::prelude::*;

pub const PLATFORM_CONFIG_SEED: &[u8] = b"platform_config";
pub const MATCH_POOL_SEED: &[u8] = b"match_pool";
pub const BET_SEED: &[u8] = b"bet";
pub const VAULT_SEED: &[u8] = b"vault";

pub const DEFAULT_FEE_BPS: u16 = 300; // 3%
pub const DEFAULT_TIMEOUT_SECONDS: i64 = 1800; // 30 minutes
pub const CLAIM_WINDOW_SECONDS: i64 = 30 * 24 * 60 * 60; // 30 days
pub const MAX_FEE_BPS: u16 = 1000; // 10% max
pub const DEFAULT_MIN_BET_LAMPORTS: u64 = 10_000_000; // 0.01 SOL
pub const DEFAULT_BETTING_WINDOW_SECONDS: i64 = 300; // 5 minutes
