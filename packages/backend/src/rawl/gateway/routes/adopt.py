from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from rawl.api.routes.pretrained import PRETRAINED_MODELS
from rawl.db.models.fighter import Fighter
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import ApiKeyAuth
from rawl.gateway.schemas import AdoptPretrainedRequest, FighterResponse
from rawl.redis_client import redis_pool
from rawl.s3_client import download_bytes

router = APIRouter(tags=["gateway-adopt"])

# Shares rate limit with submit: 3 per wallet per hour
SUBMIT_RATE_LIMIT = 3
SUBMIT_RATE_WINDOW = 3600


@router.post("/adopt", response_model=FighterResponse, status_code=201)
async def adopt_pretrained(
    db: DbSession,
    wallet: ApiKeyAuth,
    body: AdoptPretrainedRequest,
):
    """Adopt a platform pretrained model as your fighter.

    Skips validation (trusted platform model), goes straight to calibration.
    Rate limit: shares the 3/wallet/hour submit limit.
    """
    # 1. Validate pretrained_id exists in registry
    model_info = PRETRAINED_MODELS.get(body.pretrained_id)
    if model_info is None:
        raise HTTPException(status_code=404, detail="Unknown pretrained model ID")

    # 2. Rate limit check (shared with submit, atomic Lua)
    rate_key = f"ratelimit:submit:{wallet}"
    if not await redis_pool.rate_limit_check(rate_key, SUBMIT_RATE_LIMIT, SUBMIT_RATE_WINDOW):
        ttl = await redis_pool.ttl(rate_key)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded: 3 submissions per hour"},
            headers={"Retry-After": str(max(ttl, 0))},
        )

    # 3. Verify model exists in S3
    s3_key = model_info["s3_key"]
    data = await download_bytes(s3_key)
    if data is None:
        raise HTTPException(status_code=503, detail="Model not available in storage")

    # 4. Look up user
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # 5. Create fighter — game_id, character, model_path all from registry (not user input)
    # Set to "ready" with default Elo (1200) until emulation stack is live on workers,
    # then switch back to "calibrating" + dispatch run_calibration_task.
    fighter = Fighter(
        owner_id=user.id,
        name=body.name,
        game_id=model_info["game_id"],
        character=model_info["character"],
        model_path=s3_key,
        status="ready",
    )
    db.add(fighter)
    await db.commit()
    await db.refresh(fighter)

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
