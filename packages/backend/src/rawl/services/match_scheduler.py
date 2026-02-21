"""ARQ cron task that pairs queued fighters and dispatches matches."""
from __future__ import annotations

import logging

from rawl.config import settings

logger = logging.getLogger(__name__)


async def _schedule_async():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.session import worker_session_factory
    from rawl.engine.emulation_queue import enqueue_ranked
    from rawl.services.match_queue import get_active_game_ids, try_match, widen_windows

    async with worker_session_factory() as db:
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

                from rawl.db.models.match import Match

                delay = settings.pre_match_delay_seconds
                match = Match(
                    game_id=game_id,
                    match_format=settings.default_match_format,
                    fighter_a_id=fighter_a_id,
                    fighter_b_id=fighter_b_id,
                    match_type="ranked",
                    has_pool=True,
                    starts_at=datetime.now(UTC) + timedelta(seconds=delay),
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

                # Create on-chain match pool for betting
                if match.has_pool:
                    pool_ok = await _create_onchain_pool(db, match, fighter_a, fighter_b)
                    if not pool_ok:
                        match.status = "cancelled"
                        match.cancel_reason = "pool_creation_failed"
                        await db.commit()
                        logger.error(
                            "Match cancelled: on-chain pool creation failed",
                            extra={"match_id": str(match.id)},
                        )
                        continue

                # Enqueue match execution after the betting window
                await enqueue_ranked(
                    match_id=str(match.id),
                    game_id=game_id,
                    model_a=fighter_a.model_path,
                    model_b=fighter_b.model_path,
                    match_format=settings.default_match_format,
                    delay_seconds=delay,
                    p1_character=fighter_a.character or "",
                    p2_character=fighter_b.character or "",
                )
            else:
                # No pair found — widen Elo windows for next tick
                await widen_windows(game_id)


async def _create_onchain_pool(db, match, fighter_a, fighter_b) -> bool:
    """Create on-chain MatchPool PDA so users can place bets.

    Returns True on success, False on failure.
    """
    from sqlalchemy import select

    from rawl.db.models.user import User

    try:
        from rawl.evm.client import evm_client

        # Get owner wallet addresses to use as fighter identifiers on-chain
        owner_a = await db.execute(select(User).where(User.id == fighter_a.owner_id))
        owner_b = await db.execute(select(User).where(User.id == fighter_b.owner_id))
        user_a = owner_a.scalar_one_or_none()
        user_b = owner_b.scalar_one_or_none()

        if not user_a or not user_b:
            logger.error(
                "Fighter owner not found, skipping on-chain pool",
                extra={"match_id": str(match.id)},
            )
            return False

        tx_hash = await evm_client.create_match_on_chain(
            str(match.id), user_a.wallet_address, user_b.wallet_address
        )

        # Store the onchain reference for the event listener
        match.onchain_match_id = str(match.id).replace("-", "")[:32]
        await db.commit()

        logger.info(
            "On-chain match pool created",
            extra={
                "match_id": str(match.id),
                "tx_hash": tx_hash,
            },
        )
        return True
    except Exception:
        logger.exception(
            "Failed to create on-chain match pool",
            extra={"match_id": str(match.id)},
        )
        return False
