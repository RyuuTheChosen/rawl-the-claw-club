from __future__ import annotations

import uuid

from pydantic import BaseModel


class OddsResponse(BaseModel):
    match_id: uuid.UUID
    side_a_total: float
    side_b_total: float
    pool_total: float
    odds_a: float | None = None  # Display-only
    odds_b: float | None = None  # Display-only
    bet_count: int = 0
