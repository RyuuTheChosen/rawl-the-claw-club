from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FighterListResponse(BaseModel):
    id: uuid.UUID
    name: str
    game_id: str
    character: str
    elo_rating: float
    matches_played: int
    wins: int
    losses: int
    status: str


class FighterDetailResponse(FighterListResponse):
    owner_id: uuid.UUID
    adapter_version: str | None = None
    created_at: datetime
    updated_at: datetime
