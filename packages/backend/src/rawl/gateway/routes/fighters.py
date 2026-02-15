from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from rawl.db.models.fighter import Fighter
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import ApiKeyAuth
from rawl.gateway.schemas import FighterResponse

router = APIRouter(tags=["gateway-fighters"])


@router.get("/fighters", response_model=list[FighterResponse])
async def list_my_fighters(
    db: DbSession,
    wallet: ApiKeyAuth,
):
    """List all fighters owned by the authenticated user."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.owner_id == user.id).order_by(Fighter.created_at.desc())
    )
    fighters = result.scalars().all()

    return [
        FighterResponse(
            id=f.id, name=f.name, game_id=f.game_id, character=f.character,
            elo_rating=f.elo_rating, matches_played=f.matches_played,
            wins=f.wins, losses=f.losses, status=f.status, created_at=f.created_at,
        )
        for f in fighters
    ]


@router.get("/fighters/{fighter_id}", response_model=FighterResponse)
async def get_my_fighter(
    db: DbSession,
    wallet: ApiKeyAuth,
    fighter_id: uuid.UUID,
):
    """Get details of a fighter owned by the authenticated user."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.id == fighter_id, Fighter.owner_id == user.id)
    )
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")

    return FighterResponse(
        id=fighter.id, name=fighter.name, game_id=fighter.game_id,
        character=fighter.character, elo_rating=fighter.elo_rating,
        matches_played=fighter.matches_played, wins=fighter.wins,
        losses=fighter.losses, status=fighter.status, created_at=fighter.created_at,
    )


@router.post("/fighters/{fighter_id}/recalibrate")
async def recalibrate_fighter(
    db: DbSession,
    wallet: ApiKeyAuth,
    fighter_id: uuid.UUID,
):
    """Request recalibration for a fighter that failed calibration."""
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result = await db.execute(
        select(Fighter).where(Fighter.id == fighter_id, Fighter.owner_id == user.id)
    )
    fighter = result.scalar_one_or_none()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")

    if fighter.status != "calibration_failed":
        raise HTTPException(status_code=400, detail="Fighter is not in calibration_failed status")

    fighter.status = "calibrating"
    await db.commit()

    # Kick off calibration again
    # from rawl.services.elo import run_calibration
    # run_calibration.delay(str(fighter.id))

    return {"message": "Recalibration started", "fighter_id": str(fighter_id)}
