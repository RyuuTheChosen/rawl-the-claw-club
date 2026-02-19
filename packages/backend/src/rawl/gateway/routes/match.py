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
    QueueStatusResponse,
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


@router.get("/queue/{fighter_id}", response_model=QueueStatusResponse)
async def get_queue_status(
    db: DbSession,
    wallet: ApiKeyAuth,
    fighter_id: uuid.UUID,
):
    """Check if a fighter is still in the matchmaking queue."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.id == fighter_id, Fighter.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Fighter not found or not owned by you")

    import json
    import time

    from rawl.redis_client import redis_pool

    meta_raw = await redis_pool.get(f"matchqueue:meta:{fighter_id}")
    if not meta_raw:
        return QueueStatusResponse(queued=False)

    meta = json.loads(meta_raw)
    enqueued_at = meta.get("enqueued_at", time.time())
    elapsed = time.time() - enqueued_at

    game_id = meta.get("game_id", "")
    queue_size = await redis_pool.zcard(f"matchqueue:{game_id}") if game_id else 0

    return QueueStatusResponse(
        queued=True, elapsed_seconds=round(elapsed, 1), queue_size=queue_size
    )


@router.delete("/queue/{fighter_id}")
async def leave_queue(
    db: DbSession,
    wallet: ApiKeyAuth,
    fighter_id: uuid.UUID,
):
    """Remove a fighter from the matchmaking queue."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.id == fighter_id, Fighter.owner_id == user.id)
    )
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found or not owned by you")

    from rawl.services.match_queue import dequeue_fighter

    await dequeue_fighter(fighter_id, fighter.game_id)
    return {"removed": True}


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

    # Create on-chain match pool for betting
    if match.has_pool:
        try:
            from rawl.evm.client import evm_client

            # Look up owner B's wallet (owner A is the authenticated user)
            owner_b_result = await db.execute(
                select(User).where(User.id == fighter_b.owner_id)
            )
            owner_b = owner_b_result.scalar_one_or_none()
            if owner_b:
                tx_hash = await evm_client.create_match_on_chain(
                    str(match.id), user.wallet_address, owner_b.wallet_address
                )
                match.onchain_match_id = str(match.id).replace("-", "")[:32]
                await db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to create on-chain pool",
                extra={"match_id": str(match.id)},
            )

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
