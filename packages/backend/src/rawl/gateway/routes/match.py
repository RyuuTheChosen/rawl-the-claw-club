from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from rawl.db.models.fighter import Fighter
from rawl.db.models.match import Match
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import ApiKeyAuth
from rawl.gateway.schemas import (
    CreateCustomMatchRequest,
    QueueMatchRequest,
    QueueMatchResponse,
)

router = APIRouter(tags=["gateway-match"])


@router.post("/queue", response_model=QueueMatchResponse)
async def queue_for_match(
    db: DbSession,
    wallet: ApiKeyAuth,
    body: QueueMatchRequest,
):
    """Queue a fighter for matchmaking."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(
            Fighter.id == body.fighter_id,
            Fighter.owner_id == user.id,
            Fighter.status == "ready",
        )
    )
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(
            status_code=400,
            detail="Fighter not found, not owned by you, or not ready",
        )

    if fighter.game_id != body.game_id:
        raise HTTPException(
            status_code=400,
            detail=f"Fighter game_id ({fighter.game_id}) does not match request ({body.game_id})",
        )

    # Add to match queue
    from rawl.services.match_queue import enqueue_fighter
    await enqueue_fighter(
        fighter_id=fighter.id,
        game_id=body.game_id,
        match_type=body.match_type,
        elo_rating=fighter.elo_rating,
        owner_id=str(user.id),
    )

    return QueueMatchResponse(queued=True, message="Fighter queued for matchmaking")


@router.post("/match", status_code=201)
async def create_custom_match(
    db: DbSession,
    wallet: ApiKeyAuth,
    body: CreateCustomMatchRequest,
):
    """Create a custom match (pick opponent, set betting params)."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Verify fighter_a ownership
    result = await db.execute(
        select(Fighter).where(
            Fighter.id == body.fighter_a_id,
            Fighter.owner_id == user.id,
            Fighter.status == "ready",
        )
    )
    fighter_a = result.scalar_one_or_none()
    if not fighter_a:
        raise HTTPException(status_code=400, detail="Fighter A not found or not ready")

    # Verify fighter_b exists and is ready
    result = await db.execute(
        select(Fighter).where(
            Fighter.id == body.fighter_b_id,
            Fighter.status == "ready",
        )
    )
    fighter_b = result.scalar_one_or_none()
    if not fighter_b:
        raise HTTPException(status_code=400, detail="Fighter B not found or not ready")

    # Both fighters must be same game
    if fighter_a.game_id != fighter_b.game_id:
        raise HTTPException(status_code=400, detail="Fighters must be from the same game")

    # Self-matching prohibition
    if fighter_a.owner_id == fighter_b.owner_id:
        raise HTTPException(status_code=400, detail="Cannot match fighters from same owner")

    match = Match(
        game_id=fighter_a.game_id,
        match_format=body.match_format,
        fighter_a_id=body.fighter_a_id,
        fighter_b_id=body.fighter_b_id,
        match_type="challenge",
        has_pool=body.has_pool,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    # Dispatch match execution
    from rawl.engine.tasks import execute_match
    execute_match.delay(
        str(match.id),
        fighter_a.game_id,
        fighter_a.model_path,
        fighter_b.model_path,
        body.match_format,
    )

    return {
        "match_id": str(match.id),
        "game_id": match.game_id,
        "status": match.status,
    }
