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
    amount_sol: float
    onchain_bet_pda: str | None = None
    status: str
    created_at: datetime
    claimed_at: datetime | None = None


class BetWithMatchResponse(BetResponse):
    game_id: str
    fighter_a_name: str | None = None
    fighter_b_name: str | None = None
    match_status: str
    match_winner_id: uuid.UUID | None = None


_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class RecordBetRequest(BaseModel):
    wallet_address: str = Field(..., max_length=44)
    side: str = Field(..., pattern="^[ab]$")
    amount_sol: float = Field(..., gt=0)
    tx_signature: str = Field(..., max_length=128)

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_base58(cls, v: str) -> str:
        if not _BASE58_RE.fullmatch(v):
            raise ValueError("Invalid wallet address: must be base58 (32-44 chars)")
        return v
