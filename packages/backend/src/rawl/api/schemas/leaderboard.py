from __future__ import annotations

import uuid

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    fighter_id: uuid.UUID
    fighter_name: str
    owner_wallet: str
    elo_rating: float
    wins: int
    losses: int
    matches_played: int
    division: str  # Bronze, Silver, Gold, Diamond
