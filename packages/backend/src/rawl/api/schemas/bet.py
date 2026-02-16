from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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


class RecordBetRequest(BaseModel):
    wallet_address: str = Field(..., max_length=44)
    side: str = Field(..., pattern="^[ab]$")
    amount_sol: float = Field(..., gt=0)
    tx_signature: str = Field(..., max_length=128)
