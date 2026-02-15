"""Deserialize on-chain account data for MatchPool, Bet, and PlatformConfig.

Layout matches the Anchor #[account] structs in contracts/programs/rawl/src/state/.
All accounts start with an 8-byte Anchor discriminator (SHA256("account:<Name>")[:8]).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from solders.pubkey import Pubkey

# Anchor discriminators: SHA256("account:<Name>")[:8]
# Pre-computed for efficiency
MATCH_POOL_DISCRIMINATOR = b""  # Will be computed on first use
BET_DISCRIMINATOR = b""
PLATFORM_CONFIG_DISCRIMINATOR = b""


def _anchor_discriminator(name: str) -> bytes:
    import hashlib
    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


MATCH_POOL_DISC = _anchor_discriminator("MatchPool")
BET_DISC = _anchor_discriminator("Bet")
PLATFORM_CONFIG_DISC = _anchor_discriminator("PlatformConfig")


class MatchStatus:
    OPEN = 0
    LOCKED = 1
    RESOLVED = 2
    CANCELLED = 3

    _NAMES = {0: "Open", 1: "Locked", 2: "Resolved", 3: "Cancelled"}

    @classmethod
    def name(cls, value: int) -> str:
        return cls._NAMES.get(value, f"Unknown({value})")


class MatchWinner:
    NONE = 0
    SIDE_A = 1
    SIDE_B = 2

    _NAMES = {0: "None", 1: "SideA", 2: "SideB"}

    @classmethod
    def name(cls, value: int) -> str:
        return cls._NAMES.get(value, f"Unknown({value})")


class BetSide:
    SIDE_A = 0
    SIDE_B = 1


@dataclass
class MatchPoolAccount:
    match_id: bytes  # [u8; 32]
    fighter_a: Pubkey
    fighter_b: Pubkey
    side_a_total: int  # u64 lamports
    side_b_total: int  # u64 lamports
    side_a_bet_count: int  # u32
    side_b_bet_count: int  # u32
    winning_bet_count: int  # u32
    bet_count: int  # u32
    status: int  # enum MatchStatus (1 byte)
    winner: int  # enum MatchWinner (1 byte)
    oracle: Pubkey
    creator: Pubkey
    created_at: int  # i64
    lock_timestamp: int  # i64
    resolve_timestamp: int  # i64
    cancel_timestamp: int  # i64
    min_bet: int  # u64 lamports
    betting_window: int  # i64 seconds
    bump: int  # u8
    vault_bump: int  # u8


@dataclass
class BetAccount:
    bettor: Pubkey
    match_id: bytes  # [u8; 32]
    side: int  # enum BetSide (1 byte)
    amount: int  # u64 lamports
    claimed: bool
    bump: int  # u8


@dataclass
class PlatformConfigAccount:
    authority: Pubkey
    oracle: Pubkey
    fee_bps: int  # u16
    treasury: Pubkey
    paused: bool
    match_timeout: int  # i64
    bump: int  # u8


def deserialize_match_pool(data: bytes) -> MatchPoolAccount:
    """Deserialize a MatchPool account from raw bytes.

    Layout (after 8-byte discriminator):
      32  match_id
      32  fighter_a (Pubkey)
      32  fighter_b (Pubkey)
      8   side_a_total (u64)
      8   side_b_total (u64)
      4   side_a_bet_count (u32)
      4   side_b_bet_count (u32)
      4   winning_bet_count (u32)
      4   bet_count (u32)
      1   status (enum)
      1   winner (enum)
      32  oracle (Pubkey)
      32  creator (Pubkey)
      8   created_at (i64)
      8   lock_timestamp (i64)
      8   resolve_timestamp (i64)
      8   cancel_timestamp (i64)
      8   min_bet (u64)
      8   betting_window (i64)
      1   bump (u8)
      1   vault_bump (u8)
    """
    if data[:8] != MATCH_POOL_DISC:
        raise ValueError("Invalid MatchPool discriminator")

    offset = 8
    match_id = data[offset:offset + 32]; offset += 32
    fighter_a = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    fighter_b = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32

    (side_a_total, side_b_total) = struct.unpack_from("<QQ", data, offset); offset += 16
    (side_a_bet_count, side_b_bet_count, winning_bet_count, bet_count) = struct.unpack_from(
        "<IIII", data, offset
    ); offset += 16

    status = data[offset]; offset += 1
    winner = data[offset]; offset += 1

    oracle = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    creator = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32

    (created_at, lock_ts, resolve_ts, cancel_ts) = struct.unpack_from("<qqqq", data, offset)
    offset += 32

    (min_bet,) = struct.unpack_from("<Q", data, offset); offset += 8
    (betting_window,) = struct.unpack_from("<q", data, offset); offset += 8

    bump = data[offset]; offset += 1
    vault_bump = data[offset]; offset += 1

    return MatchPoolAccount(
        match_id=match_id,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        side_a_total=side_a_total,
        side_b_total=side_b_total,
        side_a_bet_count=side_a_bet_count,
        side_b_bet_count=side_b_bet_count,
        winning_bet_count=winning_bet_count,
        bet_count=bet_count,
        status=status,
        winner=winner,
        oracle=oracle,
        creator=creator,
        created_at=created_at,
        lock_timestamp=lock_ts,
        resolve_timestamp=resolve_ts,
        cancel_timestamp=cancel_ts,
        min_bet=min_bet,
        betting_window=betting_window,
        bump=bump,
        vault_bump=vault_bump,
    )


def deserialize_bet(data: bytes) -> BetAccount:
    """Deserialize a Bet account from raw bytes.

    Layout (after 8-byte discriminator):
      32  bettor (Pubkey)
      32  match_id
      1   side (enum)
      8   amount (u64)
      1   claimed (bool)
      1   bump (u8)
    """
    if data[:8] != BET_DISC:
        raise ValueError("Invalid Bet discriminator")

    offset = 8
    bettor = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    match_id = data[offset:offset + 32]; offset += 32
    side = data[offset]; offset += 1
    (amount,) = struct.unpack_from("<Q", data, offset); offset += 8
    claimed = bool(data[offset]); offset += 1
    bump = data[offset]; offset += 1

    return BetAccount(
        bettor=bettor,
        match_id=match_id,
        side=side,
        amount=amount,
        claimed=claimed,
        bump=bump,
    )


def deserialize_platform_config(data: bytes) -> PlatformConfigAccount:
    """Deserialize a PlatformConfig account from raw bytes.

    Layout (after 8-byte discriminator):
      32  authority (Pubkey)
      32  oracle (Pubkey)
      2   fee_bps (u16)
      32  treasury (Pubkey)
      1   paused (bool)
      8   match_timeout (i64)
      1   bump (u8)
    """
    if data[:8] != PLATFORM_CONFIG_DISC:
        raise ValueError("Invalid PlatformConfig discriminator")

    offset = 8
    authority = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    oracle = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    (fee_bps,) = struct.unpack_from("<H", data, offset); offset += 2
    treasury = Pubkey.from_bytes(data[offset:offset + 32]); offset += 32
    paused = bool(data[offset]); offset += 1
    (match_timeout,) = struct.unpack_from("<q", data, offset); offset += 8
    bump = data[offset]; offset += 1

    return PlatformConfigAccount(
        authority=authority,
        oracle=oracle,
        fee_bps=fee_bps,
        treasury=treasury,
        paused=paused,
        match_timeout=match_timeout,
        bump=bump,
    )
