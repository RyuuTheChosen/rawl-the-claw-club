from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from rawl.api.schemas.leaderboard import LeaderboardEntry
from rawl.api.routes.leaderboard import _get_division
from rawl.db.models.fighter import Fighter
from rawl.db.models.user import User
from rawl.dependencies import DbSession
from rawl.gateway.auth import ApiKeyAuth

router = APIRouter(tags=["gateway-leaderboard"])


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_gateway_leaderboard(
    db: DbSession,
    wallet: ApiKeyAuth,
    game_id: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
):
    """Get leaderboard (authenticated gateway endpoint)."""
    query = (
        select(Fighter, User.wallet_address)
        .join(User, Fighter.owner_id == User.id)
        .where(Fighter.game_id == game_id)
        .where(Fighter.status == "ready")
        .order_by(Fighter.elo_rating.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        LeaderboardEntry(
            rank=i + 1,
            fighter_id=fighter.id,
            fighter_name=fighter.name,
            owner_wallet=wallet_addr,
            elo_rating=fighter.elo_rating,
            wins=fighter.wins,
            losses=fighter.losses,
            matches_played=fighter.matches_played,
            division=_get_division(fighter.elo_rating),
        )
        for i, (fighter, wallet_addr) in enumerate(rows)
    ]
