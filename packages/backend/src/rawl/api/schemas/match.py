from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchResponse(BaseModel):
    id: uuid.UUID
    game_id: str
    match_format: int
    fighter_a_id: uuid.UUID
    fighter_b_id: uuid.UUID
    fighter_a_name: str | None = None
    fighter_b_name: str | None = None
    winner_id: uuid.UUID | None = None
    status: str
    match_type: str
    has_pool: bool
    match_hash: str | None = None
    side_a_total: float
    side_b_total: float
    created_at: datetime
    starts_at: datetime | None = None
    locked_at: datetime | None = None
    resolved_at: datetime | None = None


class MatchDetailResponse(MatchResponse):
    round_history: str | None = None
    replay_s3_key: str | None = None
    adapter_version: str | None = None


class CreateMatchRequest(BaseModel):
    """Internal-only endpoint for match scheduler."""
    game_id: str
    fighter_a_id: uuid.UUID
    fighter_b_id: uuid.UUID
    match_format: int = 3
    match_type: str = "ranked"
    has_pool: bool = True
