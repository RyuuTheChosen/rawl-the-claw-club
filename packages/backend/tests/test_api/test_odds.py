"""Integration tests for GET /api/odds/{match_id}."""
from __future__ import annotations

import uuid

import pytest


class TestGetOdds:
    async def test_get_odds_with_pool(self, client, seed_matches):
        # resolved match has side_a=5.0 side_b=3.0
        match_id = str(seed_matches[2].id)
        r = await client.get(f"/api/odds/{match_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["pool_total"] == 8.0
        assert data["side_a_total"] == 5.0
        assert data["side_b_total"] == 3.0
        assert data["odds_a"] == pytest.approx(8.0 / 5.0, rel=0.01)
        assert data["odds_b"] == pytest.approx(8.0 / 3.0, rel=0.01)

    async def test_get_odds_zero_sides(self, client, seed_matches):
        # open match has side_a=0.0 side_b=0.0 by default
        match_id = str(seed_matches[0].id)
        r = await client.get(f"/api/odds/{match_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["pool_total"] == 0.0
        assert data["odds_a"] is None
        assert data["odds_b"] is None

    async def test_get_odds_not_found(self, client):
        r = await client.get(f"/api/odds/{uuid.uuid4()}")
        assert r.status_code == 404
