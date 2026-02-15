from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from rawl.api.schemas.odds import OddsResponse
from rawl.db.models.match import Match
from rawl.dependencies import DbSession

router = APIRouter(tags=["odds"])


@router.get("/odds/{match_id}", response_model=OddsResponse)
async def get_odds(db: DbSession, match_id: uuid.UUID):
    """Get live odds for a match."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    pool_total = match.side_a_total + match.side_b_total

    # Calculate display-only odds
    odds_a = None
    odds_b = None
    if pool_total > 0:
        if match.side_a_total > 0:
            odds_a = round(pool_total / match.side_a_total, 2)
        if match.side_b_total > 0:
            odds_b = round(pool_total / match.side_b_total, 2)

    return OddsResponse(
        match_id=match.id,
        side_a_total=match.side_a_total,
        side_b_total=match.side_b_total,
        pool_total=pool_total,
        odds_a=odds_a,
        odds_b=odds_b,
    )
