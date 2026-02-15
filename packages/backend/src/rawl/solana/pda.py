"""PDA derivation functions matching Anchor contract seeds.

Seeds from contracts/programs/rawl/src/constants.rs:
  - PLATFORM_CONFIG_SEED = b"platform_config"
  - MATCH_POOL_SEED      = b"match_pool"
  - BET_SEED             = b"bet"
  - VAULT_SEED           = b"vault"
"""
from __future__ import annotations

import uuid

from solders.pubkey import Pubkey

from rawl.config import settings

PLATFORM_CONFIG_SEED = b"platform_config"
MATCH_POOL_SEED = b"match_pool"
BET_SEED = b"bet"
VAULT_SEED = b"vault"


def _program_id() -> Pubkey:
    return Pubkey.from_string(settings.program_id)


def match_id_to_bytes(match_id: str) -> bytes:
    """Convert a UUID string to 32 zero-padded bytes for PDA seeds."""
    return uuid.UUID(match_id).bytes.ljust(32, b"\x00")


def derive_platform_config_pda() -> tuple[Pubkey, int]:
    """Derive the singleton PlatformConfig PDA."""
    return Pubkey.find_program_address(
        [PLATFORM_CONFIG_SEED],
        _program_id(),
    )


def derive_match_pool_pda(match_id: str) -> tuple[Pubkey, int]:
    """Derive the MatchPool PDA for a given match."""
    return Pubkey.find_program_address(
        [MATCH_POOL_SEED, match_id_to_bytes(match_id)],
        _program_id(),
    )


def derive_bet_pda(match_id: str, bettor: Pubkey) -> tuple[Pubkey, int]:
    """Derive the Bet PDA for a bettor on a match."""
    return Pubkey.find_program_address(
        [BET_SEED, match_id_to_bytes(match_id), bytes(bettor)],
        _program_id(),
    )


def derive_vault_pda(match_id: str) -> tuple[Pubkey, int]:
    """Derive the Vault PDA for a match."""
    return Pubkey.find_program_address(
        [VAULT_SEED, match_id_to_bytes(match_id)],
        _program_id(),
    )
