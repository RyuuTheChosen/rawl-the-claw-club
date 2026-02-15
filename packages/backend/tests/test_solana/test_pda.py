"""Tests for PDA derivation — ensures deterministic addresses matching contract seeds."""
from __future__ import annotations

import uuid

import pytest
from solders.pubkey import Pubkey

from rawl.solana.pda import (
    MATCH_POOL_SEED,
    BET_SEED,
    VAULT_SEED,
    PLATFORM_CONFIG_SEED,
    derive_bet_pda,
    derive_match_pool_pda,
    derive_platform_config_pda,
    derive_vault_pda,
    match_id_to_bytes,
)


FIXED_MATCH_ID = "12345678-1234-1234-1234-123456789abc"
FIXED_BETTOR = Pubkey.new_unique()


class TestMatchIdToBytes:
    def test_returns_32_bytes(self):
        result = match_id_to_bytes(FIXED_MATCH_ID)
        assert len(result) == 32

    def test_starts_with_uuid_bytes(self):
        result = match_id_to_bytes(FIXED_MATCH_ID)
        expected = uuid.UUID(FIXED_MATCH_ID).bytes
        assert result[:16] == expected

    def test_padded_with_zeros(self):
        result = match_id_to_bytes(FIXED_MATCH_ID)
        assert result[16:] == b"\x00" * 16

    def test_deterministic(self):
        a = match_id_to_bytes(FIXED_MATCH_ID)
        b = match_id_to_bytes(FIXED_MATCH_ID)
        assert a == b

    def test_different_ids_differ(self):
        other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert match_id_to_bytes(FIXED_MATCH_ID) != match_id_to_bytes(other)


class TestPlatformConfigPDA:
    def test_returns_valid_pubkey_and_bump(self):
        pda, bump = derive_platform_config_pda()
        assert isinstance(pda, Pubkey)
        assert 0 <= bump <= 255

    def test_deterministic(self):
        a = derive_platform_config_pda()
        b = derive_platform_config_pda()
        assert a == b

    def test_is_off_curve(self):
        pda, _ = derive_platform_config_pda()
        # PDAs should not be on the Ed25519 curve
        assert not pda.is_on_curve()


class TestMatchPoolPDA:
    def test_returns_valid_pubkey(self):
        pda, bump = derive_match_pool_pda(FIXED_MATCH_ID)
        assert isinstance(pda, Pubkey)
        assert 0 <= bump <= 255

    def test_deterministic(self):
        a = derive_match_pool_pda(FIXED_MATCH_ID)
        b = derive_match_pool_pda(FIXED_MATCH_ID)
        assert a == b

    def test_different_match_ids_give_different_pdas(self):
        other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        pda1, _ = derive_match_pool_pda(FIXED_MATCH_ID)
        pda2, _ = derive_match_pool_pda(other)
        assert pda1 != pda2


class TestBetPDA:
    def test_returns_valid_pubkey(self):
        pda, bump = derive_bet_pda(FIXED_MATCH_ID, FIXED_BETTOR)
        assert isinstance(pda, Pubkey)
        assert 0 <= bump <= 255

    def test_deterministic(self):
        a = derive_bet_pda(FIXED_MATCH_ID, FIXED_BETTOR)
        b = derive_bet_pda(FIXED_MATCH_ID, FIXED_BETTOR)
        assert a == b

    def test_different_bettors_give_different_pdas(self):
        other_bettor = Pubkey.new_unique()
        pda1, _ = derive_bet_pda(FIXED_MATCH_ID, FIXED_BETTOR)
        pda2, _ = derive_bet_pda(FIXED_MATCH_ID, other_bettor)
        assert pda1 != pda2


class TestVaultPDA:
    def test_returns_valid_pubkey(self):
        pda, bump = derive_vault_pda(FIXED_MATCH_ID)
        assert isinstance(pda, Pubkey)
        assert 0 <= bump <= 255

    def test_deterministic(self):
        a = derive_vault_pda(FIXED_MATCH_ID)
        b = derive_vault_pda(FIXED_MATCH_ID)
        assert a == b
