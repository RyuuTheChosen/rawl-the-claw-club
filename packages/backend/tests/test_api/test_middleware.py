"""Integration tests for rate limiting and internal JWT middleware."""
from __future__ import annotations

import pytest

from tests.conftest import make_internal_token


class TestInternalJWT:
    async def test_internal_jwt_valid(self, client, seed_fighters, internal_token_header):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post("/api/matches", json=body, headers=internal_token_header)
        assert r.status_code == 201

    async def test_internal_jwt_expired(self, client, seed_fighters, expired_token_header):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post("/api/matches", json=body, headers=expired_token_header)
        assert r.status_code == 401
        assert "expired" in r.json()["detail"].lower()

    async def test_internal_jwt_missing(self, client, seed_fighters):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post("/api/matches", json=body)
        assert r.status_code == 401

    async def test_internal_jwt_invalid(self, client, seed_fighters):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post(
            "/api/matches",
            json=body,
            headers={"X-Internal-Token": "not.a.valid.jwt"},
        )
        assert r.status_code == 401


class TestRateLimit:
    async def test_rate_limit_enforced(self, client, mock_redis):
        """After exceeding limit, 429 is returned."""
        # The ASGI transport sets client IP via request.client.host
        # Pre-fill the rate limit for every plausible IP
        for ip in ["127.0.0.1", "localhost", "unknown", "test"]:
            rate_key = f"ratelimit:{ip}:GET:/api/matches"
            await mock_redis.set(rate_key, 61)
            await mock_redis.expire(rate_key, 60)

        r = await client.get("/api/matches")
        assert r.status_code == 429
        assert "Retry-After" in r.headers
