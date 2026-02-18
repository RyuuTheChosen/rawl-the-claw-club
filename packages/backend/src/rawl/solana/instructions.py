"""Build Solana instructions for all 16 Rawl contract instructions.

Each builder produces a `solders.instruction.Instruction` with:
  - Anchor discriminator: SHA256("global:<name>")[:8]
  - Serialized args (little-endian)
  - Account metas matching the Anchor #[derive(Accounts)] structs
"""
from __future__ import annotations

import hashlib
import struct

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID

from rawl.config import settings
from rawl.solana.pda import (
    derive_bet_pda,
    derive_match_pool_pda,
    derive_platform_config_pda,
    derive_vault_pda,
    match_id_to_bytes,
)


def _program_id() -> Pubkey:
    return Pubkey.from_string(settings.program_id)


def _discriminator(name: str) -> bytes:
    """Anchor instruction discriminator: SHA256("global:<name>")[:8]."""
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


# --- 1. initialize ---
def build_initialize_ix(
    authority: Pubkey,
    oracle: Pubkey,
    treasury: Pubkey,
    fee_bps: int,
    match_timeout: int,
) -> Instruction:
    platform_config_pda, _ = derive_platform_config_pda()
    data = _discriminator("initialize") + struct.pack("<Hq", fee_bps, match_timeout)
    accounts = [
        AccountMeta(platform_config_pda, is_signer=False, is_writable=True),
        AccountMeta(authority, is_signer=True, is_writable=True),
        AccountMeta(oracle, is_signer=False, is_writable=False),
        AccountMeta(treasury, is_signer=False, is_writable=False),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 2. create_match ---
def build_create_match_ix(
    match_id: str,
    fighter_a: Pubkey,
    fighter_b: Pubkey,
    creator: Pubkey,
    min_bet: int = 0,
    betting_window: int = 0,
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    vault_pda, _ = derive_vault_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = (
        _discriminator("create_match")
        + mid_bytes
        + bytes(fighter_a)
        + bytes(fighter_b)
        + struct.pack("<Qq", min_bet, betting_window)
    )
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(creator, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 3. place_bet ---
def build_place_bet_ix(
    match_id: str,
    bettor: Pubkey,
    side: int,
    amount: int,
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bettor)
    vault_pda, _ = derive_vault_pda(match_id)

    data = _discriminator("place_bet") + mid_bytes + struct.pack("<BQ", side, amount)
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(bettor, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 4. lock_match ---
def build_lock_match_ix(match_id: str, oracle: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)

    data = _discriminator("lock_match") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(oracle, is_signer=True, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 5. resolve_match ---
def build_resolve_match_ix(
    match_id: str, oracle: Pubkey, winner: int
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)

    data = _discriminator("resolve_match") + mid_bytes + struct.pack("<B", winner)
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(oracle, is_signer=True, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 6. claim_payout ---
def build_claim_payout_ix(match_id: str, bettor: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bettor)
    vault_pda, _ = derive_vault_pda(match_id)

    data = _discriminator("claim_payout") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(bettor, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 7. cancel_match ---
def build_cancel_match_ix(match_id: str, authority: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("cancel_match") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(authority, is_signer=True, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 8. timeout_match ---
def build_timeout_match_ix(match_id: str, caller: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("timeout_match") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(caller, is_signer=True, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 9. refund_bet ---
def build_refund_bet_ix(match_id: str, bettor: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bettor)
    vault_pda, _ = derive_vault_pda(match_id)

    data = _discriminator("refund_bet") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(bettor, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 10. close_bet ---
def build_close_bet_ix(match_id: str, bettor: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bettor)

    data = _discriminator("close_bet") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(bettor, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 11. close_match ---
def build_close_match_ix(match_id: str, authority: Pubkey) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    vault_pda, _ = derive_vault_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("close_match") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(authority, is_signer=True, is_writable=True),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 12. withdraw_fees ---
def build_withdraw_fees_ix(
    match_id: str, authority: Pubkey, treasury: Pubkey
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    vault_pda, _ = derive_vault_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("withdraw_fees") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(treasury, is_signer=False, is_writable=True),
        AccountMeta(authority, is_signer=True, is_writable=False),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 13. sweep_unclaimed ---
def build_sweep_unclaimed_ix(
    match_id: str,
    bet_bettor: Pubkey,
    authority: Pubkey,
    treasury: Pubkey,
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bet_bettor)
    vault_pda, _ = derive_vault_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("sweep_unclaimed") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(treasury, is_signer=False, is_writable=True),
        AccountMeta(authority, is_signer=True, is_writable=False),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 14. sweep_cancelled ---
def build_sweep_cancelled_ix(
    match_id: str,
    bet_bettor: Pubkey,
    caller: Pubkey,
) -> Instruction:
    mid_bytes = match_id_to_bytes(match_id)
    match_pool_pda, _ = derive_match_pool_pda(match_id)
    bet_pda, _ = derive_bet_pda(match_id, bet_bettor)
    vault_pda, _ = derive_vault_pda(match_id)
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("sweep_cancelled") + mid_bytes
    accounts = [
        AccountMeta(match_pool_pda, is_signer=False, is_writable=True),
        AccountMeta(bet_pda, is_signer=False, is_writable=True),
        AccountMeta(vault_pda, is_signer=False, is_writable=True),
        AccountMeta(platform_config_pda, is_signer=False, is_writable=False),
        AccountMeta(bet_bettor, is_signer=False, is_writable=True),
        AccountMeta(caller, is_signer=True, is_writable=False),
        AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)


# --- 15. update_authority ---
def build_update_authority_ix(
    current_authority: Pubkey, new_authority: Pubkey
) -> Instruction:
    platform_config_pda, _ = derive_platform_config_pda()

    data = _discriminator("update_authority")
    accounts = [
        AccountMeta(platform_config_pda, is_signer=False, is_writable=True),
        AccountMeta(current_authority, is_signer=True, is_writable=False),
        AccountMeta(new_authority, is_signer=True, is_writable=False),
    ]
    return Instruction(_program_id(), data, accounts)
