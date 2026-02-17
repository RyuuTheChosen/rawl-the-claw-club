"""Celery Beat task that pairs queued fighters and dispatches matches."""
from __future__ import annotations

import logging

from celery.exceptions import Ignore

from rawl.celery_app import celery, celery_async_run, get_sync_redis
from rawl.config import settings

logger = logging.getLogger(__name__)


@celery.task(name="rawl.services.match_scheduler.schedule_pending_matches")
def schedule_pending_matches():
    """Celery Beat task: attempt to pair queued fighters.

    Skips entirely (via sync Redis check) when no fighters are queued,
    avoiding the overhead of asyncio.run() + DB connections.
    """
    r = get_sync_redis()
    # Quick check: any matchqueue:* keys exist? (excludes matchqueue:meta:* keys)
    cursor, keys = r.scan(cursor=0, match="matchqueue:*", count=100)
    has_queue_keys = any(
        not k.startswith("matchqueue:meta:") for k in keys
    )
    if not has_queue_keys:
        # Scan may need more iterations, but first batch empty = very likely nothing queued
        while cursor and not has_queue_keys:
            cursor, keys = r.scan(cursor=cursor, match="matchqueue:*", count=100)
            has_queue_keys = any(
                not k.startswith("matchqueue:meta:") for k in keys
            )
    if not has_queue_keys:
        raise Ignore()

    celery_async_run(_schedule_async())


async def _schedule_async():
    from sqlalchemy import select

    from rawl.db.models.fighter import Fighter
    from rawl.db.session import worker_session_factory
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

                match = Match(
                    game_id=game_id,
                    match_format=settings.default_match_format,
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

                # Create on-chain match pool for betting
                if match.has_pool:
                    await _create_onchain_pool(db, match, fighter_a, fighter_b)

                # Dispatch match execution
                from rawl.engine.tasks import execute_match

                execute_match.delay(
                    str(match.id),
                    game_id,
                    fighter_a.model_path,
                    fighter_b.model_path,
                    settings.default_match_format,
                )
            else:
                # No pair found — widen Elo windows for next tick
                await widen_windows(game_id)


async def _create_onchain_pool(db, match, fighter_a, fighter_b) -> None:
    """Create on-chain MatchPool PDA so users can place bets."""
    from sqlalchemy import select

    from rawl.db.models.user import User

    try:
        from solders.pubkey import Pubkey

        from rawl.solana.client import solana_client

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
            return

        fighter_a_pubkey = Pubkey.from_string(user_a.wallet_address)
        fighter_b_pubkey = Pubkey.from_string(user_b.wallet_address)

        tx_sig = await solana_client.create_match_on_chain(
            str(match.id), fighter_a_pubkey, fighter_b_pubkey
        )

        # Store the onchain reference for the account listener
        match.onchain_match_id = match.id.hex[:32] if hasattr(match.id, 'hex') else str(match.id).replace("-", "")[:32]
        await db.commit()

        logger.info(
            "On-chain match pool created",
            extra={
                "match_id": str(match.id),
                "tx_sig": tx_sig,
            },
        )
    except Exception:
        logger.exception(
            "Failed to create on-chain match pool",
            extra={"match_id": str(match.id)},
        )
