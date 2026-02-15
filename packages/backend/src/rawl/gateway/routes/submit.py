from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from rawl.db.models.fighter import Fighter
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.game_adapters import get_adapter
from rawl.game_adapters.errors import UnknownGameError
from rawl.gateway.auth import ApiKeyAuth
from rawl.gateway.schemas import FighterResponse, SubmitFighterRequest
from rawl.redis_client import redis_pool

router = APIRouter(tags=["gateway-submit"])

# Rate limit: 3 submissions per wallet per hour
SUBMIT_RATE_LIMIT = 3
SUBMIT_RATE_WINDOW = 3600  # 1 hour in seconds


@router.post("/submit", response_model=FighterResponse, status_code=201)
async def submit_fighter(
    db: DbSession,
    wallet: ApiKeyAuth,
    body: SubmitFighterRequest,
):
    """Submit a trained fighter model for validation.

    Rate limit: 3/wallet/hour, 1 concurrent validation.
    """
    # Rate limiting: 3/wallet/hour
    rate_key = f"ratelimit:submit:{wallet}"
    current_count = await redis_pool.get(rate_key)
    if current_count is not None and int(current_count) >= SUBMIT_RATE_LIMIT:
        ttl = await redis_pool.ttl(rate_key)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded: 3 submissions per hour"},
            headers={"Retry-After": str(max(ttl, 0))},
        )

    # Validate game exists in adapter registry
    try:
        get_adapter(body.game_id)
    except UnknownGameError:
        raise HTTPException(status_code=400, detail=f"Unknown game: {body.game_id}")

    # Get user
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Create fighter in validating status
    fighter = Fighter(
        owner_id=user.id,
        name=body.name,
        game_id=body.game_id,
        character=body.character,
        model_path=body.model_s3_key,
        status="validating",
    )
    db.add(fighter)
    await db.commit()
    await db.refresh(fighter)

    # Increment rate limit counter
    count = await redis_pool.incr(rate_key)
    if count == 1:
        await redis_pool.expire(rate_key, SUBMIT_RATE_WINDOW)

    # Kick off async validation (Celery task)
    from rawl.training.validation import validate_model
    validate_model.delay(str(fighter.id), body.model_s3_key)

    return FighterResponse(
        id=fighter.id,
        name=fighter.name,
        game_id=fighter.game_id,
        character=fighter.character,
        elo_rating=fighter.elo_rating,
        matches_played=fighter.matches_played,
        wins=fighter.wins,
        losses=fighter.losses,
        status=fighter.status,
        created_at=fighter.created_at,
    )
