"""Celery Beat task that pairs queued fighters and dispatches matches."""
from __future__ import annotations

import logging

from rawl.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="rawl.services.match_scheduler.schedule_pending_matches")
def schedule_pending_matches():
    """Celery Beat task: attempt to pair queued fighters."""
    import asyncio

    asyncio.run(_schedule_async())


async def _schedule_async():
    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.models.match import Match
    from rawl.db.session import async_session_factory
    from rawl.services.match_queue import get_active_game_ids, try_match, widen_windows

    async with async_session_factory() as db:
        game_ids = await get_active_game_ids()

        for game_id in game_ids:
            pair = await try_match(game_id)
            if pair:
                fighter_a_id, fighter_b_id = pair

                # Load fighters to get model_path and match_format defaults
                result_a = await db.execute(
                    select(Fighter).where(Fighter.id == fighter_a_id)
                )
                result_b = await db.execute(
                    select(Fighter).where(Fighter.id == fighter_b_id)
                )
                fighter_a = result_a.scalar_one_or_none()
                fighter_b = result_b.scalar_one_or_none()
                if not fighter_a or not fighter_b:
                    logger.error(
                        "Paired fighter not found in DB",
                        extra={"a": fighter_a_id, "b": fighter_b_id},
                    )
                    continue

                match = Match(
                    game_id=game_id,
                    match_format="bo3",
                    fighter_a_id=fighter_a_id,
                    fighter_b_id=fighter_b_id,
                    match_type="ranked",
                    has_pool=True,
                )
                db.add(match)
                await db.commit()
                await db.refresh(match)

                logger.info(
                    "Match scheduled",
                    extra={
                        "match_id": str(match.id),
                        "game_id": game_id,
                        "fighter_a": fighter_a_id,
                        "fighter_b": fighter_b_id,
                    },
                )

                # Dispatch match execution
                from rawl.engine.tasks import execute_match

                execute_match.delay(
                    str(match.id),
                    game_id,
                    fighter_a.model_path,
                    fighter_b.model_path,
                    "bo3",
                )
            else:
                # No pair found — widen Elo windows for next tick
                await widen_windows(game_id)
