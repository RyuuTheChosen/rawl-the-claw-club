from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rawl.config import settings
from rawl.monitoring.logging_config import setup_logging

logger = logging.getLogger(__name__)


class _CORSMiddleware(CORSMiddleware):
    """CORSMiddleware that skips the Origin check for WebSocket connections.

    Starlette's CORSMiddleware does an exact-string Origin match and returns
    403 for WebSocket upgrade requests whose Origin header doesn't match.
    WebSockets don't use CORS preflight — the browser sends an Origin header,
    but enforcement is already done at the application level (per-IP connection
    limits in the broadcaster).  This subclass passes WebSocket connections
    straight through to the inner app without checking Origin.
    """

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    # Startup: initialize connections
    from rawl.db.session import engine
    from rawl.redis_client import redis_pool
    from rawl.solana.client import solana_client
    from rawl.solana.account_listener import account_listener

    await redis_pool.initialize()
    await solana_client.initialize()

    # Start account listener as background task
    listener_task = asyncio.create_task(account_listener.start())

    yield

    # Shutdown: close connections
    await account_listener.stop()
    listener_task.cancel()
    await solana_client.close()
    await redis_pool.close()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rawl",
        description="AI Fighting Game Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        _CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from rawl.api.middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

    # Register routers
    from rawl.api.router import api_router
    from rawl.gateway.router import gateway_router
    from rawl.ws.broadcaster import ws_router
    from rawl.ws.training_ws import training_ws_router

    app.include_router(api_router, prefix="/api")
    app.include_router(gateway_router, prefix="/api/gateway")
    app.include_router(ws_router, prefix="/ws")
    app.include_router(training_ws_router, prefix="/ws/gateway")

    return app
