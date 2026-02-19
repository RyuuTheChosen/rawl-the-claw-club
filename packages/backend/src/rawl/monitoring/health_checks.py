from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    component: str
    healthy: bool
    latency_ms: float | None = None
    message: str | None = None


async def check_database() -> HealthStatus:
    from sqlalchemy import text

    from rawl.db.session import engine

    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return HealthStatus("database", True, latency_ms=(time.monotonic() - start) * 1000)
    except Exception as e:
        return HealthStatus("database", False, message=str(e))


async def check_redis() -> HealthStatus:
    from rawl.redis_client import redis_pool

    start = time.monotonic()
    try:
        await redis_pool.ping()
        return HealthStatus("redis", True, latency_ms=(time.monotonic() - start) * 1000)
    except Exception as e:
        return HealthStatus("redis", False, message=str(e))


async def check_s3() -> HealthStatus:
    from rawl.config import settings
    from rawl.s3_client import _get_client

    start = time.monotonic()
    try:
        async with await _get_client() as client:
            await client.head_bucket(Bucket=settings.s3_bucket)
        return HealthStatus("s3", True, latency_ms=(time.monotonic() - start) * 1000)
    except Exception as e:
        return HealthStatus("s3", False, message=str(e))


async def check_celery() -> HealthStatus:
    """Verify Celery broker is reachable via a ping."""
    start = time.monotonic()
    try:
        from rawl.celery_app import celery

        inspector = celery.control.inspect(timeout=2.0)
        pong = inspector.ping()
        if pong:
            return HealthStatus("celery", True, latency_ms=(time.monotonic() - start) * 1000)
        return HealthStatus("celery", False, message="No workers responded to ping")
    except Exception as e:
        return HealthStatus("celery", False, message=str(e))


async def check_base_rpc() -> HealthStatus:
    """Check that Base RPC is reachable."""
    start = time.monotonic()
    try:
        from rawl.evm.client import evm_client

        ok = await evm_client.get_health()
        if ok:
            return HealthStatus(
                "base_rpc", True, latency_ms=(time.monotonic() - start) * 1000
            )
        return HealthStatus("base_rpc", False, message="RPC unhealthy: is_connected returned False")
    except Exception as e:
        return HealthStatus("base_rpc", False, message=str(e))


async def check_retro() -> HealthStatus:
    """Check that stable-retro is importable and the ROM is available."""
    from rawl.config import settings

    start = time.monotonic()
    try:
        import stable_retro

        stable_retro.data.get_romfile_path(settings.retro_game)
        return HealthStatus(
            "retro",
            True,
            latency_ms=(time.monotonic() - start) * 1000,
            message=f"ROM found: {settings.retro_game}",
        )
    except FileNotFoundError:
        return HealthStatus("retro", False, message=f"ROM not found: {settings.retro_game}")
    except Exception as e:
        return HealthStatus("retro", False, message=str(e))


async def check_match_queue() -> HealthStatus:
    """Report number of fighters currently queued."""
    start = time.monotonic()
    try:
        from rawl.services.match_queue import get_active_game_ids

        game_ids = await get_active_game_ids()
        return HealthStatus(
            "match_queue",
            True,
            latency_ms=(time.monotonic() - start) * 1000,
            message=f"{len(game_ids)} active game queues",
        )
    except Exception as e:
        return HealthStatus("match_queue", False, message=str(e))


async def check_active_matches() -> HealthStatus:
    """Count currently running matches."""
    from sqlalchemy import func, select

    start = time.monotonic()
    try:
        from rawl.db.models.match import Match
        from rawl.db.session import async_session_factory

        async with async_session_factory() as db:
            result = await db.execute(
                select(func.count()).select_from(Match).where(
                    Match.status.in_(["pending", "running"])
                )
            )
            count = result.scalar() or 0
        return HealthStatus(
            "active_matches",
            True,
            latency_ms=(time.monotonic() - start) * 1000,
            message=f"{count} active matches",
        )
    except Exception as e:
        return HealthStatus("active_matches", False, message=str(e))


async def get_all_health() -> list[HealthStatus]:
    results = []
    for check in [
        check_database,
        check_redis,
        check_s3,
        check_celery,
        check_base_rpc,
        check_retro,
        check_match_queue,
        check_active_matches,
    ]:
        try:
            results.append(await check())
        except Exception as e:
            results.append(HealthStatus(check.__name__.replace("check_", ""), False, message=str(e)))
    return results
