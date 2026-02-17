from __future__ import annotations

import logging
import time

from celery.exceptions import Ignore

from rawl.celery_app import celery, celery_async_run, get_sync_redis

logger = logging.getLogger(__name__)

# If no heartbeat for this many seconds, match runner is declared dead
HEARTBEAT_TIMEOUT = 60


@celery.task(name="rawl.services.health_checker.check_match_heartbeats")
def check_match_heartbeats():
    """Celery Beat task: runs every 30 seconds.

    Checks Redis heartbeat timestamps for all active Match Runners.
    If no heartbeat for 60 seconds -> declared dead.

    Skips entirely when no heartbeat keys exist in Redis.
    """
    r = get_sync_redis()
    cursor, keys = r.scan(cursor=0, match="heartbeat:match:*", count=100)
    has_heartbeats = bool(keys)
    while cursor and not has_heartbeats:
        cursor, keys = r.scan(cursor=cursor, match="heartbeat:match:*", count=100)
        has_heartbeats = bool(keys)
    if not has_heartbeats:
        raise Ignore()

    celery_async_run(_check_heartbeats_async())


async def _check_heartbeats_async():
    from sqlalchemy import select

    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.redis_client import redis_pool

    try:
        # Find all active matches (locked status)
        async with worker_session_factory() as db:
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
                    async with worker_session_factory() as db:
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
