from __future__ import annotations

import asyncio
from typing import Coroutine

from celery import Celery
from celery.schedules import crontab

from rawl.config import settings


def celery_async_run(coro: Coroutine):
    """Run an async coroutine from a Celery task.

    Disposes the SQLAlchemy engine's connection pool first to avoid
    'Future attached to a different loop' errors when Celery reuses
    forked workers across multiple asyncio.run() calls.
    """
    async def _wrapper():
        from rawl.db.session import engine
        await engine.dispose()
        return await coro
    return asyncio.run(_wrapper())

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
        "schedule": 15.0,
    },
    "match-scheduler": {
        "task": "rawl.services.match_scheduler.schedule_pending_matches",
        "schedule": 10.0,
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
