"""Tests for Solana account deserialization with known byte patterns."""
from __future__ import annotations

import struct

import pytest
from solders.pubkey import Pubkey

from rawl.solana.deserialize import (
    BET_DISC,
    MATCH_POOL_DISC,
    PLATFORM_CONFIG_DISC,
    BetAccount,
    MatchPoolAccount,
    PlatformConfigAccount,
    deserialize_bet,
    deserialize_match_pool,
    deserialize_platform_config,
)


def _make_pubkey_bytes(seed: int = 1) -> bytes:
    """Create deterministic 32-byte pubkey data."""
    return bytes([seed] * 32)


class TestDeserializeMatchPool:
    def _build_data(self, **overrides) -> bytes:
        """Build valid MatchPool binary data."""
        defaults = {
            "match_id": b"\x01" * 32,
            "fighter_a": _make_pubkey_bytes(2),
            "fighter_b": _make_pubkey_bytes(3),
            "side_a_total": 1_000_000_000,
            "side_b_total": 2_000_000_000,
            "side_a_bet_count": 5,
            "side_b_bet_count": 3,
            "winning_bet_count": 0,
            "bet_count": 8,
            "status": 0,  # Open
            "winner": 0,  # None
            "oracle": _make_pubkey_bytes(4),
            "creator": _make_pubkey_bytes(5),
            "created_at": 1700000000,
            "lock_timestamp": 0,
            "resolve_timestamp": 0,
            "cancel_timestamp": 0,
            "bump": 254,
            "vault_bump": 253,
        }
        defaults.update(overrides)
        d = defaults

        buf = bytearray(MATCH_POOL_DISC)
        buf += d["match_id"]
        buf += d["fighter_a"]
        buf += d["fighter_b"]
        buf += struct.pack("<QQ", d["side_a_total"], d["side_b_total"])
        buf += struct.pack(
            "<IIII",
            d["side_a_bet_count"],
            d["side_b_bet_count"],
            d["winning_bet_count"],
            d["bet_count"],
        )
        buf += bytes([d["status"], d["winner"]])
        buf += d["oracle"]
        buf += d["creator"]
        buf += struct.pack(
            "<qqqq",
            d["created_at"],
            d["lock_timestamp"],
            d["resolve_timestamp"],
            d["cancel_timestamp"],
        )
        buf += bytes([d["bump"], d["vault_bump"]])
        return bytes(buf)

    def test_deserializes_correctly(self):
        data = self._build_data()
        result = deserialize_match_pool(data)
        assert isinstance(result, MatchPoolAccount)
        assert result.side_a_total == 1_000_000_000
        assert result.side_b_total == 2_000_000_000
        assert result.side_a_bet_count == 5
        assert result.bet_count == 8
        assert result.status == 0
        assert result.bump == 254
        assert result.vault_bump == 253

    def test_invalid_discriminator_raises(self):
        data = b"\x00" * 8 + b"\x00" * 250
        with pytest.raises(ValueError, match="Invalid MatchPool discriminator"):
            deserialize_match_pool(data)

    def test_locked_status(self):
        data = self._build_data(status=1, lock_timestamp=1700001000)
        result = deserialize_match_pool(data)
        assert result.status == 1
        assert result.lock_timestamp == 1700001000


class TestDeserializeBet:
    def _build_data(self, **overrides) -> bytes:
        defaults = {
            "bettor": _make_pubkey_bytes(10),
            "match_id": b"\x02" * 32,
            "side": 0,
            "amount": 500_000_000,
            "claimed": False,
            "bump": 252,
        }
        defaults.update(overrides)
        d = defaults

        buf = bytearray(BET_DISC)
        buf += d["bettor"]
        buf += d["match_id"]
        buf += bytes([d["side"]])
        buf += struct.pack("<Q", d["amount"])
        buf += bytes([1 if d["claimed"] else 0])
        buf += bytes([d["bump"]])
        return bytes(buf)

    def test_deserializes_correctly(self):
        data = self._build_data()
        result = deserialize_bet(data)
        assert isinstance(result, BetAccount)
        assert result.amount == 500_000_000
        assert result.side == 0
        assert result.claimed is False
        assert result.bump == 252

    def test_claimed_bet(self):
        data = self._build_data(claimed=True, side=1)
        result = deserialize_bet(data)
        assert result.claimed is True
        assert result.side == 1

    def test_invalid_discriminator_raises(self):
        data = b"\xff" * 8 + b"\x00" * 80
        with pytest.raises(ValueError, match="Invalid Bet discriminator"):
            deserialize_bet(data)


class TestDeserializePlatformConfig:
    def _build_data(self, **overrides) -> bytes:
        defaults = {
            "authority": _make_pubkey_bytes(20),
            "oracle": _make_pubkey_bytes(21),
            "fee_bps": 300,
            "treasury": _make_pubkey_bytes(22),
            "paused": False,
            "match_timeout": 1800,
            "bump": 251,
        }
        defaults.update(overrides)
        d = defaults

        buf = bytearray(PLATFORM_CONFIG_DISC)
        buf += d["authority"]
        buf += d["oracle"]
        buf += struct.pack("<H", d["fee_bps"])
        buf += d["treasury"]
        buf += bytes([1 if d["paused"] else 0])
        buf += struct.pack("<q", d["match_timeout"])
        buf += bytes([d["bump"]])
        return bytes(buf)

    def test_deserializes_correctly(self):
        data = self._build_data()
        result = deserialize_platform_config(data)
        assert isinstance(result, PlatformConfigAccount)
        assert result.fee_bps == 300
        assert result.match_timeout == 1800
        assert result.paused is False
        assert result.bump == 251

    def test_paused_platform(self):
        data = self._build_data(paused=True, fee_bps=500)
        result = deserialize_platform_config(data)
        assert result.paused is True
        assert result.fee_bps == 500
