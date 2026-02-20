"""Integration tests for POST /api/gateway/submit."""
from __future__ import annotations

import pytest


class TestSubmitFighter:
    async def test_submit_fighter_success(self, client, seed_user, api_key_header):
        body = {
            "name": "TestSubmitBot",
            "game_id": "sf2ce",
            "character": "Ryu",
            "model_s3_key": "models/test_submit.zip",
        }
        r = await client.post(
            "/api/gateway/submit", json=body, headers=api_key_header
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "TestSubmitBot"
        assert data["status"] == "validating"

    async def test_submit_unknown_game(self, client, seed_user, api_key_header):
        body = {
            "name": "BadGameBot",
            "game_id": "nonexistent_game",
            "character": "X",
            "model_s3_key": "models/bad.zip",
        }
        r = await client.post(
            "/api/gateway/submit", json=body, headers=api_key_header
        )
        assert r.status_code == 400

    async def test_submit_no_auth(self, client):
        body = {
            "name": "NoAuthBot",
            "game_id": "sf2ce",
            "character": "Ryu",
            "model_s3_key": "models/noauth.zip",
        }
        r = await client.post("/api/gateway/submit", json=body)
        assert r.status_code == 401

    async def test_submit_rate_limit(self, client, seed_user, api_key_header, mock_redis):
        """4th submission within the hour → 429."""
        wallet = seed_user.wallet_address
        rate_key = f"ratelimit:submit:{wallet}"
        # Pre-set the counter to 3 (limit)
        await mock_redis.set(rate_key, 3)
        await mock_redis.expire(rate_key, 3600)

        body = {
            "name": "RateLimitBot",
            "game_id": "sf2ce",
            "character": "Ryu",
            "model_s3_key": "models/rl.zip",
        }
        r = await client.post(
            "/api/gateway/submit", json=body, headers=api_key_header
        )
        assert r.status_code == 429
