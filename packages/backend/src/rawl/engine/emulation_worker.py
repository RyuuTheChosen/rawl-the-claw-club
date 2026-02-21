"""Emulation worker — multiprocessing consumer of match execution queues.

Queues (priority order):
  rawl:emulation:queue       — ranked matches (high priority)
  rawl:emulation:queue:cal   — calibration matches (only when below MAX_CONCURRENT)

Reliability:
  Jobs are claimed via LMOVE to a processing list.
  On startup, stale processing-list items are re-queued (crash recovery).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from multiprocessing import Process

import redis

logger = logging.getLogger(__name__)

MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_MATCHES", "4"))
POLL_INTERVAL  = 0.2  # seconds between queue checks when all slots are busy

RANKED_QUEUE      = "rawl:emulation:queue"
CAL_QUEUE         = "rawl:emulation:queue:cal"
RANKED_PROCESSING = "rawl:emulation:processing"
CAL_PROCESSING    = "rawl:emulation:processing:cal"
HEALTH_KEY        = "rawl:emulation:health-check"
HEALTH_TTL        = 30   # seconds; if worker dies, key expires within this window
HEALTH_INTERVAL   = 50   # write heartbeat every N poll ticks (~10s at 0.2s/tick)


# ── Subprocess entry point ─────────────────────────────────────────────────────

def run_match_process(job: dict, processing_key: str, raw_payload: str) -> None:
    """Runs inside a spawned OS process — owns its own asyncio event loop."""

    async def _run():
        from rawl.evm.client import evm_client
        from rawl.redis_client import redis_pool

        await evm_client.initialize()
        try:
            if job["job_type"] == "match":
                from rawl.engine.tasks import _execute_match_async
                await _execute_match_async(
                    match_id=job["match_id"],
                    game_id=job["game_id"],
                    fighter_a_model=job["fighter_a_model"],
                    fighter_b_model=job["fighter_b_model"],
                    match_format=job.get("match_format", 3),
                    p1_character=job.get("p1_character", ""),
                    p2_character=job.get("p2_character", ""),
                )
            elif job["job_type"] == "calibration":
                from rawl.engine.tasks import _run_calibration_async
                await _run_calibration_async(fighter_id=job["fighter_id"])
            else:
                logger.error("Unknown job_type, discarding", extra={"job": job})
        finally:
            # Remove from processing list on completion (success or failure)
            r_sync = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
            r_sync.lrem(processing_key, 1, raw_payload)
            await evm_client.close()
            await redis_pool.close()

    asyncio.run(_run())


# ── Crash recovery ─────────────────────────────────────────────────────────────

def recover_stale_jobs(r: redis.Redis) -> None:
    """On startup, re-queue any jobs left in processing lists from a previous crash."""
    for src, dst in [
        (RANKED_PROCESSING, RANKED_QUEUE),
        (CAL_PROCESSING,    CAL_QUEUE),
    ]:
        stale = r.lrange(src, 0, -1)
        for item in stale:
            r.rpush(dst, item)
            r.lrem(src, 1, item)
            logger.warning("Re-queued stale job from processing list", extra={"queue": src})


# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    from rawl.config import settings
    from rawl.monitoring.logging_config import setup_logging

    setup_logging()

    r = redis.from_url(settings.redis_url, decode_responses=True)
    recover_stale_jobs(r)

    active: list[Process] = []
    shutdown_requested = False

    def _handle_signal(signum, frame):
        nonlocal shutdown_requested
        logger.info("Signal received — draining active matches before exit")
        shutdown_requested = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Emulation worker started", extra={"max_concurrent": MAX_CONCURRENT})

    tick = 0
    while not shutdown_requested:
        # Reap finished processes
        active = [p for p in active if p.is_alive()]

        # Write heartbeat key so API health check can detect this worker
        tick += 1
        if tick % HEALTH_INTERVAL == 1:
            r.set(HEALTH_KEY, "1", ex=HEALTH_TTL)

        if len(active) < MAX_CONCURRENT:
            # Try ranked queue first (high priority)
            raw = r.lmove(RANKED_QUEUE, RANKED_PROCESSING, "LEFT", "RIGHT")
            processing_key = RANKED_PROCESSING

            # Only serve calibration when there's remaining capacity
            if raw is None:
                raw = r.lmove(CAL_QUEUE, CAL_PROCESSING, "LEFT", "RIGHT")
                processing_key = CAL_PROCESSING

            if raw is not None:
                try:
                    job = json.loads(raw)
                except json.JSONDecodeError:
                    logger.error("Malformed job payload, discarding", extra={"raw": raw[:200]})
                    r.lrem(processing_key, 1, raw)
                    continue

                job_id = job.get("match_id") or job.get("fighter_id", "unknown")
                logger.info(
                    "Spawning process for job",
                    extra={"job_type": job.get("job_type"), "id": job_id},
                )
                p = Process(
                    target=run_match_process,
                    args=(job, processing_key, raw),
                    daemon=False,  # non-daemon so SIGTERM waits for children
                    name=f"emulation-{job_id[:8]}",
                )
                p.start()
                active.append(p)
                continue  # immediately check for more work

        time.sleep(POLL_INTERVAL)

    # Graceful shutdown: wait for all active matches to finish
    logger.info("Waiting for active matches to complete", extra={"count": len(active)})
    for p in active:
        p.join(timeout=2500)  # slightly over the 40-min soft limit
    logger.info("Emulation worker stopped")


if __name__ == "__main__":
    main()
