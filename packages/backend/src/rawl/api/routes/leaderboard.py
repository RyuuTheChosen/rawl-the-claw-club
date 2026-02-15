from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from rawl.api.schemas.leaderboard import LeaderboardEntry
from rawl.db.models.fighter import Fighter
from rawl.db.models.user import User
from rawl.dependencies import DbSession

router = APIRouter(tags=["leaderboard"])


def _get_division(elo: float) -> str:
    if elo >= 1600:
        return "Diamond"
    if elo >= 1400:
        return "Gold"
    if elo >= 1200:
        return "Silver"
    return "Bronze"


@router.get("/leaderboard/{game_id}", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    db: DbSession,
    game_id: str,
    limit: int = Query(50, ge=1, le=100),
):
    """Get leaderboard for a specific game."""
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
            owner_wallet=wallet,
            elo_rating=fighter.elo_rating,
            wins=fighter.wins,
            losses=fighter.losses,
            matches_played=fighter.matches_played,
            division=_get_division(fighter.elo_rating),
        )
        for i, (fighter, wallet) in enumerate(rows)
    ]
