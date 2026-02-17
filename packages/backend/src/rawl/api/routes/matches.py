from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import aliased

from rawl.api.middleware import InternalAuth
from rawl.api.schemas.common import CursorParams, PaginatedResponse
from rawl.api.schemas.match import CreateMatchRequest, MatchDetailResponse, MatchResponse
from rawl.db.models.fighter import Fighter
from rawl.db.models.match import Match
from rawl.dependencies import DbSession

router = APIRouter(tags=["matches"])


def _match_to_response(row: Match, name_a: str | None, name_b: str | None) -> MatchResponse:
    data = {c.key: getattr(row, c.key) for c in Match.__table__.columns}
    data["fighter_a_name"] = name_a
    data["fighter_b_name"] = name_b
    return MatchResponse.model_validate(data)


@router.get("/matches", response_model=PaginatedResponse[MatchResponse])
async def list_matches(
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    game: str | None = Query(None),
    match_type: str | None = Query(None, alias="type"),
    fighter_id: uuid.UUID | None = Query(None),
):
    """List matches with cursor-based pagination."""
    params = CursorParams(cursor=cursor, limit=limit)

    fa = aliased(Fighter, name="fa")
    fb = aliased(Fighter, name="fb")
    query = (
        select(Match, fa.name.label("fighter_a_name"), fb.name.label("fighter_b_name"))
        .outerjoin(fa, Match.fighter_a_id == fa.id)
        .outerjoin(fb, Match.fighter_b_id == fb.id)
    )

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
    if fighter_id:
        conditions.append(
            or_(Match.fighter_a_id == fighter_id, Match.fighter_b_id == fighter_id)
        )

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
    rows = result.all()

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        last_match = items[-1][0]
        next_cursor = CursorParams.encode_cursor(last_match.created_at, str(last_match.id))

    return PaginatedResponse(
        items=[_match_to_response(m, na, nb) for m, na, nb in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/matches/{match_id}", response_model=MatchDetailResponse)
async def get_match(db: DbSession, match_id: uuid.UUID):
    """Get match details by ID."""
    fa = aliased(Fighter, name="fa")
    fb = aliased(Fighter, name="fb")
    query = (
        select(Match, fa.name.label("fighter_a_name"), fb.name.label("fighter_b_name"))
        .outerjoin(fa, Match.fighter_a_id == fa.id)
        .outerjoin(fb, Match.fighter_b_id == fb.id)
        .where(Match.id == match_id)
    )
    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    match, name_a, name_b = row
    data = {c.key: getattr(match, c.key) for c in Match.__table__.columns}
    data["fighter_a_name"] = name_a
    data["fighter_b_name"] = name_b
    return MatchDetailResponse.model_validate(data)


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
