from __future__ import annotations

import logging
import time

from rawl.celery_app import celery

logger = logging.getLogger(__name__)

# If no heartbeat for this many seconds, match runner is declared dead
HEARTBEAT_TIMEOUT = 60


@celery.task(name="rawl.services.health_checker.check_match_heartbeats")
def check_match_heartbeats():
    """Celery Beat task: runs every 15 seconds.

    Checks Redis heartbeat timestamps for all active Match Runners.
    If no heartbeat for 60 seconds → declared dead.
    Submits cancel_match on-chain with CANCELLED_FAILURE.
    """
    import asyncio
    asyncio.run(_check_heartbeats_async())


async def _check_heartbeats_async():
    from rawl.redis_client import redis_pool
    from rawl.db.session import async_session_factory
    from rawl.db.models.match import Match
    from sqlalchemy import select

    try:
        # Find all active matches (locked status)
        async with async_session_factory() as db:
            result = await db.execute(
                select(Match).where(Match.status == "locked")
            )
            active_matches = result.scalars().all()

        now = time.time()

        for match in active_matches:
            match_id = str(match.id)
            heartbeat_key = f"heartbeat:match:{match_id}"

            try:
                last_beat = await redis_pool.get(heartbeat_key)
                if last_beat is None:
                    # No heartbeat ever recorded — may be just starting
                    continue

                last_beat_time = float(last_beat)
                elapsed = now - last_beat_time

                if elapsed > HEARTBEAT_TIMEOUT:
                    logger.error(
                        "Match runner heartbeat timeout",
                        extra={
                            "match_id": match_id,
                            "elapsed_seconds": round(elapsed, 1),
                        },
                    )

                    # Cancel match on-chain
                    from rawl.engine.oracle_client import oracle_client
                    try:
                        await oracle_client.submit_cancel(match_id, reason="heartbeat_timeout")
                    except NotImplementedError:
                        pass  # Solana integration not yet connected

                    # Update DB status
                    async with async_session_factory() as db:
                        result = await db.execute(
                            select(Match).where(Match.id == match.id)
                        )
                        m = result.scalar_one_or_none()
                        if m:
                            m.status = "cancelled"
                            m.cancel_reason = "CANCELLED_FAILURE"
                            await db.commit()

            except Exception:
                logger.exception(
                    "Error checking heartbeat",
                    extra={"match_id": match_id},
                )

    except Exception:
        logger.exception("Health checker task failed")
