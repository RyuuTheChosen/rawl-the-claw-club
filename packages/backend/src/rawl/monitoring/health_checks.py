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


async def check_solana_rpc() -> HealthStatus:
    """Check that Solana RPC is reachable."""
    from rawl.config import settings

    start = time.monotonic()
    try:
        from solana.rpc.async_api import AsyncClient

        async with AsyncClient(settings.solana_rpc_url) as client:
            resp = await client.get_health()
            ok = resp.value == "ok" if hasattr(resp, "value") else True
            if ok:
                return HealthStatus(
                    "solana_rpc", True, latency_ms=(time.monotonic() - start) * 1000
                )
            return HealthStatus("solana_rpc", False, message=f"RPC unhealthy: {resp}")
    except Exception as e:
        return HealthStatus("solana_rpc", False, message=str(e))


async def check_diambra() -> HealthStatus:
    """Check that the DIAMBRA Docker image is available."""
    import asyncio

    from rawl.config import settings

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "image", "inspect", settings.diambra_image,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5.0)
        if proc.returncode == 0:
            return HealthStatus("diambra", True, latency_ms=(time.monotonic() - start) * 1000)
        return HealthStatus("diambra", False, message=f"Image not found: {settings.diambra_image}")
    except Exception as e:
        return HealthStatus("diambra", False, message=str(e))


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
        check_solana_rpc,
        check_diambra,
        check_match_queue,
        check_active_matches,
    ]:
        try:
            results.append(await check())
        except Exception as e:
            results.append(HealthStatus(check.__name__.replace("check_", ""), False, message=str(e)))
    return results
