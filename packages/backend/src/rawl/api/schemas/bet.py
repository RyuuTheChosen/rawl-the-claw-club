from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BetResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    wallet_address: str
    side: str
    amount_eth: float
    onchain_bet_id: str | None = None
    status: str
    created_at: datetime
    claimed_at: datetime | None = None


class BetWithMatchResponse(BetResponse):
    game_id: str
    fighter_a_name: str | None = None
    fighter_b_name: str | None = None
    match_status: str
    match_winner_id: uuid.UUID | None = None
    winner_side: str | None = None  # "a", "b", or null


_EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class RecordBetRequest(BaseModel):
    wallet_address: str = Field(..., max_length=42)
    side: str = Field(..., pattern="^[ab]$")
    amount_eth: float = Field(..., gt=0)
    tx_hash: str = Field(..., max_length=66)

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_evm(cls, v: str) -> str:
        if not _EVM_ADDRESS_RE.fullmatch(v):
            raise ValueError("Invalid wallet address: must be EVM format (0x + 40 hex chars)")
        return v
