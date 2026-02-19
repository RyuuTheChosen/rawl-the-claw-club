#!/usr/bin/env python3
"""Generate Anchor IDL JSON for the Rawl program (Anchor 0.30.1 format).

Workaround for anchor-syn 0.30.1 source_file() incompatibility with modern Rust.
"""
import hashlib
import json


def disc(prefix: str, name: str) -> list[int]:
    """Compute 8-byte Anchor discriminator: sha256(prefix:name)[..8]"""
    h = hashlib.sha256(f"{prefix}:{name}".encode()).digest()
    return list(h[:8])


def ix_disc(name: str) -> list[int]:
    return disc("global", name)


def acct_disc(name: str) -> list[int]:
    return disc("account", name)


def evt_disc(name: str) -> list[int]:
    return disc("event", name)


IDL = {
    "address": "AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K",
    "metadata": {
        "name": "rawl",
        "version": "0.1.0",
        "spec": "0.1.0",
        "description": "Rawl - AI Fighting Game Betting Platform",
    },
    "instructions": [
        {
            "name": "initialize",
            "discriminator": ix_disc("initialize"),
            "accounts": [
                {"name": "platform_config", "writable": True, "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "authority", "writable": True, "signer": True},
                {"name": "oracle"},
                {"name": "treasury"},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "fee_bps", "type": "u16"},
                {"name": "match_timeout", "type": "i64"},
            ],
        },
        {
            "name": "create_match",
            "discriminator": ix_disc("create_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "creator", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
                {"name": "fighter_a", "type": "pubkey"},
                {"name": "fighter_b", "type": "pubkey"},
                {"name": "min_bet", "type": "u64"},
                {"name": "betting_window", "type": "i64"},
            ],
        },
        {
            "name": "place_bet",
            "discriminator": ix_disc("place_bet"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bettor", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
                {"name": "side", "type": "u8"},
                {"name": "amount", "type": "u64"},
            ],
        },
        {
            "name": "lock_match",
            "discriminator": ix_disc("lock_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "oracle", "signer": True},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "resolve_match",
            "discriminator": ix_disc("resolve_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "oracle", "signer": True},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
                {"name": "winner", "type": "u8"},
            ],
        },
        {
            "name": "claim_payout",
            "discriminator": ix_disc("claim_payout"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bettor", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "cancel_match",
            "discriminator": ix_disc("cancel_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "authority", "signer": True},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "timeout_match",
            "discriminator": ix_disc("timeout_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "caller", "signer": True},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "refund_bet",
            "discriminator": ix_disc("refund_bet"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bettor", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "refund_no_winners",
            "discriminator": ix_disc("refund_no_winners"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bettor", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "close_bet",
            "discriminator": ix_disc("close_bet"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bettor"},
                    ]
                }},
                {"name": "bettor", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "close_match",
            "discriminator": ix_disc("close_match"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "authority", "writable": True, "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "withdraw_fees",
            "discriminator": ix_disc("withdraw_fees"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "treasury", "writable": True},
                {"name": "authority", "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "sweep_unclaimed",
            "discriminator": ix_disc("sweep_unclaimed"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bet.bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "treasury", "writable": True},
                {"name": "authority", "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "sweep_cancelled",
            "discriminator": ix_disc("sweep_cancelled"),
            "accounts": [
                {"name": "match_pool", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"match_pool")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "bet", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"bet")},
                        {"kind": "arg", "path": "match_id"},
                        {"kind": "account", "path": "bet.bettor"},
                    ]
                }},
                {"name": "vault", "writable": True, "pda": {
                    "seeds": [
                        {"kind": "const", "value": list(b"vault")},
                        {"kind": "arg", "path": "match_id"},
                    ]
                }},
                {"name": "platform_config", "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "bettor_dest", "writable": True},
                {"name": "caller", "signer": True},
                {"name": "system_program", "address": "11111111111111111111111111111111"},
            ],
            "args": [
                {"name": "match_id", "type": {"array": ["u8", 32]}},
            ],
        },
        {
            "name": "update_authority",
            "discriminator": ix_disc("update_authority"),
            "accounts": [
                {"name": "platform_config", "writable": True, "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "current_authority", "signer": True},
                {"name": "new_authority", "signer": True},
            ],
            "args": [],
        },
        {
            "name": "update_config",
            "discriminator": ix_disc("update_config"),
            "accounts": [
                {"name": "platform_config", "writable": True, "pda": {
                    "seeds": [{"kind": "const", "value": list(b"platform_config")}]
                }},
                {"name": "authority", "signer": True},
            ],
            "args": [
                {"name": "fee_bps", "type": {"option": "u16"}},
                {"name": "match_timeout", "type": {"option": "i64"}},
                {"name": "paused", "type": {"option": "bool"}},
                {"name": "oracle", "type": {"option": "pubkey"}},
                {"name": "treasury", "type": {"option": "pubkey"}},
            ],
        },
    ],
    "accounts": [
        {"name": "MatchPool", "discriminator": acct_disc("MatchPool")},
        {"name": "Bet", "discriminator": acct_disc("Bet")},
        {"name": "PlatformConfig", "discriminator": acct_disc("PlatformConfig")},
    ],
    "events": [
        {"name": "MatchCreated", "discriminator": evt_disc("MatchCreated")},
        {"name": "BetPlaced", "discriminator": evt_disc("BetPlaced")},
        {"name": "MatchLocked", "discriminator": evt_disc("MatchLocked")},
        {"name": "MatchResolved", "discriminator": evt_disc("MatchResolved")},
        {"name": "PayoutClaimed", "discriminator": evt_disc("PayoutClaimed")},
        {"name": "MatchCancelled", "discriminator": evt_disc("MatchCancelled")},
        {"name": "BetRefunded", "discriminator": evt_disc("BetRefunded")},
        {"name": "FeesWithdrawn", "discriminator": evt_disc("FeesWithdrawn")},
        {"name": "ConfigUpdated", "discriminator": evt_disc("ConfigUpdated")},
    ],
    "errors": [
        {"code": 6000, "name": "Unauthorized", "msg": "Unauthorized: only the platform authority can perform this action"},
        {"code": 6001, "name": "OracleUnauthorized", "msg": "Unauthorized: only the oracle can perform this action"},
        {"code": 6002, "name": "InvalidMatchStatus", "msg": "Match is not in the expected status"},
        {"code": 6003, "name": "MatchNotOpen", "msg": "Match is not open for betting"},
        {"code": 6004, "name": "MatchNotLocked", "msg": "Match is not locked"},
        {"code": 6005, "name": "MatchNotResolved", "msg": "Match is not resolved"},
        {"code": 6006, "name": "MatchNotCancelled", "msg": "Match is not cancelled"},
        {"code": 6007, "name": "ZeroBetAmount", "msg": "Bet amount must be greater than zero"},
        {"code": 6008, "name": "BetOnLosingSide", "msg": "Bet is on the losing side"},
        {"code": 6009, "name": "AlreadyClaimed", "msg": "Bet has already been claimed"},
        {"code": 6010, "name": "TimeoutNotElapsed", "msg": "Match timeout has not elapsed"},
        {"code": 6011, "name": "ClaimWindowNotElapsed", "msg": "Claim window has not elapsed"},
        {"code": 6012, "name": "Overflow", "msg": "Arithmetic overflow"},
        {"code": 6013, "name": "InvalidFeeBps", "msg": "Invalid fee basis points"},
        {"code": 6014, "name": "InvalidSide", "msg": "Invalid side"},
        {"code": 6015, "name": "PlatformPaused", "msg": "Platform is paused"},
        {"code": 6016, "name": "BetCountNotZero", "msg": "Bet count not zero"},
        {"code": 6017, "name": "WinningBetCountNotZero", "msg": "Winning bet count not zero for fee withdrawal"},
        {"code": 6018, "name": "BetBelowMinimum", "msg": "Bet amount is below the minimum"},
        {"code": 6019, "name": "BettingWindowClosed", "msg": "Betting window has closed"},
        {"code": 6020, "name": "FeesAlreadyWithdrawn", "msg": "Fees have already been withdrawn for this match"},
        {"code": 6021, "name": "InsufficientVault", "msg": "Vault has insufficient balance for this operation"},
        {"code": 6022, "name": "InvalidTimeout", "msg": "Match timeout must be positive"},
        {"code": 6023, "name": "InvalidBettingWindow", "msg": "Betting window must not be negative"},
        {"code": 6024, "name": "WinnersExist", "msg": "Winners exist — use claim_payout instead"},
    ],
    "types": [
        {
            "name": "MatchPool",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "fighter_a", "type": "pubkey"},
                    {"name": "fighter_b", "type": "pubkey"},
                    {"name": "side_a_total", "type": "u64"},
                    {"name": "side_b_total", "type": "u64"},
                    {"name": "side_a_bet_count", "type": "u32"},
                    {"name": "side_b_bet_count", "type": "u32"},
                    {"name": "winning_bet_count", "type": "u32"},
                    {"name": "bet_count", "type": "u32"},
                    {"name": "status", "type": {"defined": {"name": "MatchStatus"}}},
                    {"name": "winner", "type": {"defined": {"name": "MatchWinner"}}},
                    {"name": "oracle", "type": "pubkey"},
                    {"name": "creator", "type": "pubkey"},
                    {"name": "created_at", "type": "i64"},
                    {"name": "lock_timestamp", "type": "i64"},
                    {"name": "resolve_timestamp", "type": "i64"},
                    {"name": "cancel_timestamp", "type": "i64"},
                    {"name": "min_bet", "type": "u64"},
                    {"name": "betting_window", "type": "i64"},
                    {"name": "bump", "type": "u8"},
                    {"name": "vault_bump", "type": "u8"},
                    {"name": "fees_withdrawn", "type": "bool"},
                    {"name": "fee_bps", "type": "u16"},
                ],
            },
        },
        {
            "name": "Bet",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "bettor", "type": "pubkey"},
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "side", "type": {"defined": {"name": "BetSide"}}},
                    {"name": "amount", "type": "u64"},
                    {"name": "claimed", "type": "bool"},
                    {"name": "bump", "type": "u8"},
                ],
            },
        },
        {
            "name": "PlatformConfig",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "authority", "type": "pubkey"},
                    {"name": "oracle", "type": "pubkey"},
                    {"name": "fee_bps", "type": "u16"},
                    {"name": "treasury", "type": "pubkey"},
                    {"name": "paused", "type": "bool"},
                    {"name": "match_timeout", "type": "i64"},
                    {"name": "bump", "type": "u8"},
                ],
            },
        },
        {
            "name": "MatchStatus",
            "type": {
                "kind": "enum",
                "variants": [
                    {"name": "Open"},
                    {"name": "Locked"},
                    {"name": "Resolved"},
                    {"name": "Cancelled"},
                ],
            },
        },
        {
            "name": "MatchWinner",
            "type": {
                "kind": "enum",
                "variants": [
                    {"name": "None"},
                    {"name": "SideA"},
                    {"name": "SideB"},
                ],
            },
        },
        {
            "name": "BetSide",
            "type": {
                "kind": "enum",
                "variants": [
                    {"name": "SideA"},
                    {"name": "SideB"},
                ],
            },
        },
        # Event types
        {
            "name": "MatchCreated",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "fighter_a", "type": "pubkey"},
                    {"name": "fighter_b", "type": "pubkey"},
                ],
            },
        },
        {
            "name": "BetPlaced",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "bettor", "type": "pubkey"},
                    {"name": "side", "type": "u8"},
                    {"name": "amount", "type": "u64"},
                ],
            },
        },
        {
            "name": "MatchLocked",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                ],
            },
        },
        {
            "name": "MatchResolved",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "winner", "type": "u8"},
                ],
            },
        },
        {
            "name": "PayoutClaimed",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "bettor", "type": "pubkey"},
                    {"name": "amount", "type": "u64"},
                ],
            },
        },
        {
            "name": "MatchCancelled",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                ],
            },
        },
        {
            "name": "BetRefunded",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "bettor", "type": "pubkey"},
                    {"name": "amount", "type": "u64"},
                ],
            },
        },
        {
            "name": "FeesWithdrawn",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "match_id", "type": {"array": ["u8", 32]}},
                    {"name": "amount", "type": "u64"},
                ],
            },
        },
        {
            "name": "ConfigUpdated",
            "type": {
                "kind": "struct",
                "fields": [
                    {"name": "field", "type": "string"},
                    {"name": "value", "type": "u64"},
                ],
            },
        },
    ],
}


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "..", "target", "idl")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "rawl.json")
    with open(out_path, "w") as f:
        json.dump(IDL, f, indent=2)
    print(f"IDL written to {out_path}")
    print(f"  {len(IDL['instructions'])} instructions")
    print(f"  {len(IDL['accounts'])} accounts")
    print(f"  {len(IDL['events'])} events")
    print(f"  {len(IDL['errors'])} errors")
    print(f"  {len(IDL['types'])} types")
