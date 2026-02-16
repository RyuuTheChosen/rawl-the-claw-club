"""Celery tasks for match execution."""
from __future__ import annotations

import logging

from rawl.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="rawl.engine.tasks.execute_match", bind=True)
def execute_match(
    self,
    match_id: str,
    game_id: str,
    fighter_a_model: str,
    fighter_b_model: str,
    match_format: int = 3,
):
    """Celery task: execute a full match.

    Sync wrapper around async match runner following the pattern in health_checker.py.
    On success: updates Elo via services/elo.py, updates Match status.
    """
    import asyncio
    asyncio.run(
        _execute_match_async(match_id, game_id, fighter_a_model, fighter_b_model, match_format)
    )


async def _execute_match_async(
    match_id: str,
    game_id: str,
    fighter_a_model: str,
    fighter_b_model: str,
    match_format: int,
):
    from rawl.engine.match_runner import run_match
    from rawl.db.session import async_session_factory
    from rawl.db.models.match import Match
    from rawl.services.elo import update_elo_after_match
    from sqlalchemy import select
    from datetime import datetime, timezone

    result = await run_match(
        match_id=match_id,
        game_id=game_id,
        fighter_a_model_path=fighter_a_model,
        fighter_b_model_path=fighter_b_model,
        match_format=match_format,
    )

    async with async_session_factory() as db:
        stmt = select(Match).where(Match.id == match_id)
        row = await db.execute(stmt)
        match = row.scalar_one_or_none()
        if not match:
            logger.error("Match not found in DB", extra={"match_id": match_id})
            return

        if result:
            match.status = "resolved"
            match.match_hash = result.match_hash
            match.hash_version = result.hash_version
            match.adapter_version = result.adapter_version
            match.round_history = str(result.round_history)
            match.resolved_at = datetime.now(timezone.utc)

            # Determine winner_id
            if result.winner == "P1":
                match.winner_id = match.fighter_a_id
            elif result.winner == "P2":
                match.winner_id = match.fighter_b_id

            await db.commit()

            # Update Elo ratings
            try:
                if result.winner == "P1":
                    winner_id = str(match.fighter_a_id)
                    loser_id = str(match.fighter_b_id)
                else:
                    winner_id = str(match.fighter_b_id)
                    loser_id = str(match.fighter_a_id)

                await update_elo_after_match(
                    winner_id=winner_id,
                    loser_id=loser_id,
                    db_session=db,
                )
            except Exception:
                logger.exception("Elo update failed", extra={"match_id": match_id})

            logger.info(
                "Match completed successfully",
                extra={
                    "match_id": match_id,
                    "winner": result.winner,
                    "hash": result.match_hash[:16],
                },
            )
        else:
            if match.status != "cancelled":
                match.status = "cancelled"
                match.cancel_reason = "engine_failure"
            await db.commit()
            logger.warning("Match failed or was cancelled", extra={"match_id": match_id})


@celery.task(name="rawl.engine.tasks.run_calibration_task", bind=True)
def run_calibration_task(self, fighter_id: str):
    """Celery task: run calibration matches for a fighter."""
    import asyncio

    asyncio.run(_run_calibration_async(fighter_id))


async def _run_calibration_async(fighter_id: str):
    from rawl.db.session import async_session_factory
    from rawl.services.elo import run_calibration

    async with async_session_factory() as db:
        success = await run_calibration(fighter_id, db)
        logger.info(
            "Calibration task finished",
            extra={"fighter_id": fighter_id, "success": success},
        )


@celery.task(name="rawl.engine.tasks.seasonal_reset_task")
def seasonal_reset_task():
    """Celery Beat task: quarterly seasonal reset for all ready fighters."""
    import asyncio

    asyncio.run(_seasonal_reset_async())


async def _seasonal_reset_async():
    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.session import async_session_factory
    from rawl.services.elo import get_division, seasonal_reset

    async with async_session_factory() as db:
        result = await db.execute(
            select(Fighter).where(Fighter.status == "ready")
        )
        fighters = result.scalars().all()

        reset_count = 0
        for fighter in fighters:
            old_elo = fighter.elo_rating
            fighter.elo_rating = seasonal_reset(old_elo)
            fighter.division_tier = get_division(fighter.elo_rating)
            reset_count += 1

        await db.commit()

        logger.info(
            "Seasonal reset completed",
            extra={"fighters_reset": reset_count},
        )


@celery.task(name="rawl.engine.tasks.retry_failed_uploads_task")
def retry_failed_uploads_task():
    """Celery Beat task: retry failed S3 uploads."""
    import asyncio

    asyncio.run(_retry_failed_uploads_async())


async def _retry_failed_uploads_async():
    from rawl.engine.failed_upload_handler import retry_failed_uploads

    retried = await retry_failed_uploads()
    if retried:
        logger.info("Retried failed uploads", extra={"count": retried})
