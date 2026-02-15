from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select, and_

from rawl.api.schemas.common import CursorParams, PaginatedResponse
from rawl.api.schemas.match import CreateMatchRequest, MatchDetailResponse, MatchResponse
from rawl.api.middleware import InternalAuth
from rawl.db.models.match import Match
from rawl.dependencies import DbSession

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=PaginatedResponse[MatchResponse])
async def list_matches(
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    game: str | None = Query(None),
    match_type: str | None = Query(None, alias="type"),
):
    """List matches with cursor-based pagination."""
    params = CursorParams(cursor=cursor, limit=limit)
    query = select(Match)

    # Filters
    conditions = []
    if status and status != "all":
        status_map = {"upcoming": "open", "live": "locked", "completed": "resolved"}
        db_status = status_map.get(status, status)
        conditions.append(Match.status == db_status)
    if game:
        conditions.append(Match.game_id == game)
    if match_type and match_type != "all":
        conditions.append(Match.match_type == match_type)

    if conditions:
        query = query.where(and_(*conditions))

    # Cursor-based pagination
    decoded = params.decode_cursor()
    if decoded:
        ts, mid = decoded
        query = query.where(
            (Match.created_at < ts) | ((Match.created_at == ts) & (Match.id < uuid.UUID(mid)))
        )

    query = query.order_by(Match.created_at.desc(), Match.id.desc()).limit(limit + 1)

    result = await db.execute(query)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = CursorParams.encode_cursor(last.created_at, str(last.id))

    return PaginatedResponse(
        items=[MatchResponse.model_validate(m, from_attributes=True) for m in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/matches/{match_id}", response_model=MatchDetailResponse)
async def get_match(db: DbSession, match_id: uuid.UUID):
    """Get match details by ID."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchDetailResponse.model_validate(match, from_attributes=True)


@router.post("/matches", response_model=MatchResponse, status_code=201)
async def create_match(
    db: DbSession,
    body: CreateMatchRequest,
    _auth: InternalAuth,
):
    """Create a new match (internal scheduler only, requires internal JWT)."""
    match = Match(
        game_id=body.game_id,
        fighter_a_id=body.fighter_a_id,
        fighter_b_id=body.fighter_b_id,
        match_format=body.match_format,
        match_type=body.match_type,
        has_pool=body.has_pool,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return MatchResponse.model_validate(match, from_attributes=True)
