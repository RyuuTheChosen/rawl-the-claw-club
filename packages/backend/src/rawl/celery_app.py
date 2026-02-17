from __future__ import annotations

import asyncio
from collections.abc import Coroutine

import redis
from celery import Celery
from celery.schedules import crontab

from rawl.config import settings


def celery_async_run(coro: Coroutine):
    """Run an async coroutine from a Celery task.

    Each asyncio.run() creates a new event loop.  The async Redis client must
    be freshly initialised on that loop and properly closed *before* the loop
    shuts down, otherwise orphaned connections carry stale Futures that blow up
    on the next invocation with "attached to a different loop".
    """
    from rawl.redis_client import redis_pool

    redis_pool.reset()  # drop old pool ref (old loop is dead, can't await close)

    async def _wrapper():
        try:
            return await coro
        finally:
            await redis_pool.close()  # cleanly shut down connections on THIS loop

    return asyncio.run(_wrapper())


# Sync Redis client for cheap guard checks in Celery tasks.
# Avoids spinning up asyncio.run() when there's nothing to do.
_sync_redis: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


celery = Celery(
    "rawl",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    "health-check": {
        "task": "rawl.services.health_checker.check_match_heartbeats",
        "schedule": 30.0,
    },
    "match-scheduler": {
        "task": "rawl.services.match_scheduler.schedule_pending_matches",
        "schedule": 30.0,
    },
    "retry-failed-uploads": {
        "task": "rawl.engine.tasks.retry_failed_uploads_task",
        "schedule": crontab(minute="*/5"),
    },
    "seasonal-reset": {
        "task": "rawl.engine.tasks.seasonal_reset_task",
        "schedule": crontab(
            month_of_year=settings.seasonal_reset_cron_month,
            day_of_month=settings.seasonal_reset_cron_day,
            hour=settings.seasonal_reset_cron_hour,
            minute=settings.seasonal_reset_cron_minute,
        ),
    },
}

# Import tasks so they are registered
celery.autodiscover_tasks(["rawl.engine"])
celery.conf.include = [
    "rawl.services.match_scheduler",
    "rawl.services.health_checker",
    "rawl.training.worker",
    "rawl.training.validation",
]
