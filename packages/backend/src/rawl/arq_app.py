"""ARQ worker — async task queue replacing Celery.

Cron jobs run inline (no separate beat process).
Heavy emulation jobs go to emulation_worker via Redis lists.
"""
from __future__ import annotations

from arq import cron, func
from arq.connections import RedisSettings

from rawl.config import settings


async def startup(ctx):
    from rawl.evm.client import evm_client
    from rawl.redis_client import redis_pool

    await redis_pool.initialize()
    await evm_client.initialize()


async def shutdown(ctx):
    from rawl.evm.client import evm_client
    from rawl.redis_client import redis_pool

    await evm_client.close()
    await redis_pool.close()


# ── Cron wrappers ──────────────────────────────────────────────────────────────

async def schedule_pending_matches(ctx):
    from rawl.services.match_scheduler import _schedule_async
    await _schedule_async()


async def promote_ready_matches(ctx):
    from rawl.engine.emulation_queue import promote_ready
    await promote_ready()


async def check_match_heartbeats(ctx):
    from rawl.services.health_checker import _check_heartbeats_async
    await _check_heartbeats_async()


async def reconcile_bets(ctx):
    from rawl.services.bet_reconciler import _reconcile_bets_async
    await _reconcile_bets_async()


async def timeout_stale_matches(ctx):
    from rawl.services.bet_reconciler import _timeout_stale_matches_async
    await _timeout_stale_matches_async()


async def retry_failed_uploads(ctx):
    from rawl.engine.failed_upload_handler import retry_failed_uploads as _retry
    await _retry()


async def seasonal_reset(ctx):
    from rawl.engine.tasks import _seasonal_reset_async
    await _seasonal_reset_async()


# ── Enqueued task functions ────────────────────────────────────────────────────

async def validate_model(ctx, fighter_id: str, model_s3_key: str):
    from rawl.training.validation import _validate_async
    await _validate_async(fighter_id, model_s3_key)


async def normalize_pretrained_models(ctx):
    from rawl.engine.tasks import _normalize_pretrained_async
    await _normalize_pretrained_async()


async def run_training(ctx, job_id: str):
    raise NotImplementedError(
        "On-platform training has been removed. "
        "Use the external training package, then submit via POST /api/gateway/submit."
    )


# ── Worker settings ────────────────────────────────────────────────────────────

class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    job_timeout = 300  # 5 min; no emulation jobs run here

    functions = [
        func(validate_model,              name="validate_model",              timeout=300),
        func(normalize_pretrained_models, name="normalize_pretrained_models", timeout=1800),
        func(run_training,                name="run_training",                timeout=10),
    ]

    cron_jobs = [
        cron(schedule_pending_matches, second={0, 30},                                unique=True),
        cron(promote_ready_matches,    second={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
                                                                                      unique=True),
        cron(check_match_heartbeats,   second=0,                                      unique=True),
        cron(reconcile_bets,           second=0,                                      unique=True),
        cron(timeout_stale_matches,    second=30,                                     unique=True),
        cron(retry_failed_uploads,     minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
                                       second=0,                                      unique=True),
        cron(seasonal_reset,           month={1, 4, 7, 10}, day=1, hour=0, minute=0,
                                       second=0,                                      unique=True),
    ]
