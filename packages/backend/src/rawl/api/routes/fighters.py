from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from rawl.api.schemas.common import PaginatedResponse
from rawl.api.schemas.fighter import FighterDetailResponse, FighterListResponse
from rawl.db.models.fighter import Fighter
from rawl.dependencies import DbSession

router = APIRouter(tags=["fighters"])


@router.get("/fighters", response_model=PaginatedResponse[FighterListResponse])
async def list_fighters(
    db: DbSession,
    game: str | None = Query(None),
    owner: str | None = Query(None, description="Filter by owner wallet address"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
):
    """List fighters with optional game/owner filter."""
    query = select(Fighter).where(Fighter.status == "ready")

    if game:
        query = query.where(Fighter.game_id == game)

    if owner:
        from rawl.db.models.user import User

        user_result = await db.execute(select(User).where(User.wallet_address == owner))
        user = user_result.scalar_one_or_none()
        if user:
            query = query.where(Fighter.owner_id == user.id)
        else:
            # Unknown wallet — return empty
            return PaginatedResponse(items=[], has_more=False)

    query = query.order_by(Fighter.elo_rating.desc()).limit(limit + 1)

    result = await db.execute(query)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]

    return PaginatedResponse(
        items=[FighterListResponse.model_validate(f, from_attributes=True) for f in items],
        has_more=has_more,
    )


@router.get("/fighters/{fighter_id}", response_model=FighterDetailResponse)
async def get_fighter(db: DbSession, fighter_id: uuid.UUID):
    """Get fighter details by ID."""
    result = await db.execute(select(Fighter).where(Fighter.id == fighter_id))
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")
    return FighterDetailResponse.model_validate(fighter, from_attributes=True)
