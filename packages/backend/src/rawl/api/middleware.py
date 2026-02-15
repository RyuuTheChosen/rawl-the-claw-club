from __future__ import annotations

import logging
import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from rawl.config import settings
from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

# Rate limit configuration per SDD Section 5.5
RATE_LIMITS: dict[str, tuple[int, int]] = {
    # endpoint_prefix: (max_requests, window_seconds)
    "GET:/api/matches": (60, 60),
    "GET:/api/fighters": (30, 60),
    "GET:/api/leaderboard": (30, 60),
    "GET:/api/odds": (120, 60),
    # Gateway has a blanket 60/min per API key
}

SUBMIT_RATE_LIMIT = (3, 3600)  # 3 per wallet per hour


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis sliding window rate limiter."""

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        client_ip = _get_client_ip(request)
        method = request.method
        path = request.url.path

        # Find matching rate limit
        limit_key = None
        max_requests = 0
        window = 0

        for prefix, (mr, ws) in RATE_LIMITS.items():
            req_method, req_path = prefix.split(":", 1)
            if method == req_method and path.startswith(req_path):
                limit_key = f"ratelimit:{client_ip}:{prefix}"
                max_requests = mr
                window = ws
                break

        if limit_key:
            allowed, retry_after = await _check_rate_limit(limit_key, max_requests, window)
            if not allowed:
                return Response(
                    content='{"detail":"Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)


async def _check_rate_limit(key: str, max_requests: int, window: int) -> tuple[bool, int]:
    """Redis sliding window counter. Returns (allowed, retry_after_seconds)."""
    try:
        current = await redis_pool.incr(key)
        if current == 1:
            await redis_pool.expire(key, window)

        if current > max_requests:
            ttl = await redis_pool.ttl(key)
            return False, max(1, ttl)

        return True, 0
    except Exception:
        # If Redis is down, allow the request
        logger.warning("Rate limit check failed, allowing request")
        return True, 0


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


# --- Internal JWT for SSR ---

def create_internal_token() -> str:
    """Generate an internal JWT for Next.js SSR requests."""
    payload = {
        "iss": "rawl-frontend",
        "exp": int(time.time()) + settings.internal_jwt_expiry_seconds,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.internal_jwt_secret, algorithm="HS256")


async def validate_internal_token(
    x_internal_token: Annotated[str | None, Header()] = None,
) -> bool:
    """Validate internal JWT from SSR requests."""
    if not x_internal_token:
        raise HTTPException(status_code=401, detail="Missing X-Internal-Token")

    try:
        jwt.decode(
            x_internal_token,
            settings.internal_jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iss"]},
        )
        return True
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Internal token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid internal token")


InternalAuth = Annotated[bool, Depends(validate_internal_token)]
