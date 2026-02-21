"""Async match execution functions called by the emulation worker."""
from __future__ import annotations

import logging
from datetime import UTC

logger = logging.getLogger(__name__)


async def _execute_match_async(
    match_id: str,
    game_id: str,
    fighter_a_model: str,
    fighter_b_model: str,
    match_format: int,
    p1_character: str = "",
    p2_character: str = "",
):
    from datetime import datetime

    from sqlalchemy import select

    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.engine.match_runner import run_match
    from rawl.services.elo import update_elo_after_match

    result = await run_match(
        match_id=match_id,
        game_id=game_id,
        fighter_a_model_path=fighter_a_model,
        fighter_b_model_path=fighter_b_model,
        match_format=match_format,
        p1_character=p1_character,
        p2_character=p2_character,
    )

    async with worker_session_factory() as db:
        stmt = select(Match).where(Match.id == match_id)
        row = await db.execute(stmt)
        match = row.scalar_one_or_none()
        if not match:
            logger.error("Match not found in DB", extra={"match_id": match_id})
            return

        if result:
            # Use savepoint so match result + Elo update commit atomically
            async with db.begin_nested():
                match.status = "resolved"
                match.match_hash = result.match_hash
                match.hash_version = result.hash_version
                match.adapter_version = result.adapter_version
                match.round_history = str(result.round_history)
                if result.replay_uploaded:
                    match.replay_s3_key = f"replays/{match_id}.mjpeg"
                else:
                    logger.warning(
                        "Match resolved without replay",
                        extra={"match_id": match_id},
                    )
                match.resolved_at = datetime.now(UTC)
                if result.locked_at and match.locked_at is None:
                    match.locked_at = result.locked_at

                # Determine winner_id
                if result.winner == "P1":
                    match.winner_id = match.fighter_a_id
                    winner_id = str(match.fighter_a_id)
                    loser_id = str(match.fighter_b_id)
                elif result.winner == "P2":
                    match.winner_id = match.fighter_b_id
                    winner_id = str(match.fighter_b_id)
                    loser_id = str(match.fighter_a_id)
                else:
                    logger.error(
                        "Invalid winner value",
                        extra={"match_id": match_id, "winner": result.winner},
                    )
                    match.status = "cancelled"
                    match.cancel_reason = "invalid_winner"
                    await db.commit()
                    return

                await update_elo_after_match(
                    winner_id=winner_id,
                    loser_id=loser_id,
                    db_session=db,
                )
            await db.commit()

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


async def _run_calibration_async(fighter_id: str):
    from rawl.db.session import worker_session_factory
    from rawl.services.elo import run_calibration

    async with worker_session_factory() as db:
        success = await run_calibration(fighter_id, db)
        logger.info(
            "Calibration task finished",
            extra={"fighter_id": fighter_id, "success": success},
        )


async def _seasonal_reset_async():
    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.session import worker_session_factory
    from rawl.services.elo import get_division, seasonal_reset

    async with worker_session_factory() as db:
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


async def _normalize_pretrained_async():
    from rawl.api.routes.pretrained import PRETRAINED_MODELS
    from rawl.config import settings
    from rawl.engine.model_normalizer import normalize_model

    success = 0
    failed = 0

    # Pretrained models
    for model_id, info in PRETRAINED_MODELS.items():
        s3_key = info["s3_key"]
        logger.info("Normalizing pretrained model", extra={"model_id": model_id})
        model = await normalize_model(s3_key)
        if model is not None:
            success += 1
        else:
            failed += 1
            logger.error("Failed to normalize pretrained model", extra={"model_id": model_id})

    # Reference models (used for calibration)
    for elo in settings.calibration_reference_elo_list:
        s3_key = f"reference/sf2ce/{elo}"
        logger.info("Normalizing reference model", extra={"elo": elo})
        model = await normalize_model(s3_key)
        if model is not None:
            success += 1
        else:
            failed += 1
            logger.error("Failed to normalize reference model", extra={"elo": elo})

    logger.info(
        "Normalization migration complete",
        extra={"success": success, "failed": failed},
    )
