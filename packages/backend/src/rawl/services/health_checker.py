from __future__ import annotations

import logging
import time

from rawl.celery_app import celery, celery_async_run

logger = logging.getLogger(__name__)

# If no heartbeat for this many seconds, match runner is declared dead
HEARTBEAT_TIMEOUT = 60


@celery.task(name="rawl.services.health_checker.check_match_heartbeats")
def check_match_heartbeats():
    """Celery Beat task: runs every 30 seconds.

    Checks Redis heartbeat timestamps for all active Match Runners.
    If no heartbeat for 60 seconds -> declared dead.
    Also catches matches where the engine never started (no heartbeat key at all).
    """
    celery_async_run(_check_heartbeats_async())


async def _check_heartbeats_async():
    from datetime import UTC, datetime

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

        if not active_matches:
            return

        now = time.time()

        for match in active_matches:
            match_id = str(match.id)
            heartbeat_key = f"heartbeat:match:{match_id}"
            reason = None

            try:
                last_beat = await redis_pool.get(heartbeat_key)

                if last_beat is None:
                    # No heartbeat ever recorded — engine may not have started yet.
                    # Use locked_at (or created_at for legacy rows) as reference.
                    lock_time = (match.locked_at or match.created_at).timestamp()
                    elapsed = now - lock_time
                    if elapsed < HEARTBEAT_TIMEOUT * 2:
                        continue  # grace period — engine may still be starting
                    reason = "engine_never_started"
                    logger.error(
                        "Match runner never started (no heartbeat recorded)",
                        extra={"match_id": match_id, "elapsed_seconds": round(elapsed, 1)},
                    )
                else:
                    elapsed = now - float(last_beat)
                    if elapsed <= HEARTBEAT_TIMEOUT:
                        continue  # healthy
                    reason = "heartbeat_timeout"
                    logger.error(
                        "Match runner heartbeat timeout",
                        extra={"match_id": match_id, "elapsed_seconds": round(elapsed, 1)},
                    )

                # Cancel match on-chain
                from rawl.engine.oracle_client import oracle_client
                try:
                    await oracle_client.submit_cancel(match_id, reason=reason)
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
                        m.cancel_reason = reason
                        m.cancelled_at = datetime.now(UTC)
                        await db.commit()

            except Exception:
                logger.exception(
                    "Error checking heartbeat",
                    extra={"match_id": match_id},
                )

    except Exception:
        logger.exception("Health checker task failed")
