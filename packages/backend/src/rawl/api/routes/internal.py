from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from rawl.monitoring.health_checks import get_all_health

router = APIRouter(tags=["internal"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    checks = await get_all_health()
    all_healthy = all(c.healthy for c in checks)
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": [
            {
                "component": c.component,
                "healthy": c.healthy,
                "latency_ms": c.latency_ms,
                "message": c.message,
            }
            for c in checks
        ],
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    try:
        from prometheus_client import REGISTRY, generate_latest

        return PlainTextResponse(
            generate_latest(REGISTRY),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except ImportError:
        return PlainTextResponse("# prometheus_client not installed\n")
