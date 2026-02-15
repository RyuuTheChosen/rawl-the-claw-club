from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from rawl.config import settings

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
}

# Import tasks so they are registered
celery.autodiscover_tasks(
    [
        "rawl.engine",
        "rawl.training",
        "rawl.services",
    ]
)
