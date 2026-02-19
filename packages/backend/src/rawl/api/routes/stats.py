from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from sqlalchemy import func, select

from rawl.api.schemas.stats import PlatformStatsResponse
from rawl.db.models.fighter import Fighter
from rawl.db.models.match import Match
from rawl.dependencies import DbSession
from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])

CACHE_KEY = "platform:stats"
CACHE_TTL = 60  # seconds


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(db: DbSession) -> PlatformStatsResponse:
    """Return aggregated platform statistics with 60s Redis cache."""
    # Try cache first
    try:
        cached = await redis_pool.get(CACHE_KEY)
        if cached is not None:
            return PlatformStatsResponse.model_validate(json.loads(cached.decode("utf-8")))
    except Exception:
        logger.warning("Redis cache read failed for stats", exc_info=True)

    # Query DB
    try:
        total_matches = (await db.execute(select(func.count()).select_from(Match))).scalar_one()
        active_fighters = (
            await db.execute(
                select(func.count()).select_from(Fighter).where(Fighter.status == "ready")
            )
        ).scalar_one()
        volume_raw = (
            await db.execute(
                select(func.coalesce(func.sum(Match.side_a_total + Match.side_b_total), 0.0)).where(
                    Match.has_pool.is_(True)
                )
            )
        ).scalar_one()
        live_matches = (
            await db.execute(
                select(func.count()).select_from(Match).where(Match.status == "locked")
            )
        ).scalar_one()

        data = PlatformStatsResponse(
            total_matches=total_matches,
            active_fighters=active_fighters,
            total_volume_lamports=int(volume_raw),
            live_matches=live_matches,
        )

        # Populate cache
        try:
            await redis_pool.set(CACHE_KEY, json.dumps(data.model_dump()), ex=CACHE_TTL)
        except Exception:
            logger.warning("Redis cache write failed for stats", exc_info=True)

        return data

    except Exception:
        logger.exception("Stats SQL query failed")
        # Try stale cache
        try:
            cached = await redis_pool.get(CACHE_KEY)
            if cached is not None:
                return PlatformStatsResponse.model_validate(json.loads(cached.decode("utf-8")))
        except Exception:
            pass
        # No cache, return zeros
        return PlatformStatsResponse(
            total_matches=0, active_fighters=0, total_volume_lamports=0, live_matches=0
        )
