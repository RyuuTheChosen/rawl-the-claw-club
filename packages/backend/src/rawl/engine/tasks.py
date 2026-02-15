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
                await update_elo_after_match(
                    fighter_a_id=str(match.fighter_a_id),
                    fighter_b_id=str(match.fighter_b_id),
                    winner=result.winner,
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
