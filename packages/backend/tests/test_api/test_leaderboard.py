"""Integration tests for GET /api/leaderboard/{game_id}."""
from __future__ import annotations

import pytest


class TestLeaderboard:
    async def test_leaderboard_sorted_by_elo(self, client, seed_fighters):
        r = await client.get("/api/leaderboard/sf2ce")
        assert r.status_code == 200
        entries = r.json()
        elos = [e["elo_rating"] for e in entries]
        assert elos == sorted(elos, reverse=True)

    async def test_leaderboard_only_ready_fighters(self, client, seed_fighters):
        r = await client.get("/api/leaderboard/sf2ce")
        entries = r.json()
        # sf2ce has 2 ready (ReadyBot, OpponentBot) + 1 validating
        assert len(entries) == 2

    async def test_leaderboard_divisions_correct(self, client, seed_fighters):
        r = await client.get("/api/leaderboard/sf2ce")
        for entry in r.json():
            elo = entry["elo_rating"]
            div = entry["division"]
            if elo >= 1600:
                assert div == "Diamond"
            elif elo >= 1400:
                assert div == "Gold"
            elif elo >= 1200:
                assert div == "Silver"
            else:
                assert div == "Bronze"

    async def test_leaderboard_limit_respected(self, client, seed_fighters):
        r = await client.get("/api/leaderboard/sf2ce", params={"limit": 1})
        assert len(r.json()) == 1

    async def test_leaderboard_rank_order(self, client, seed_fighters):
        r = await client.get("/api/leaderboard/sf2ce")
        entries = r.json()
        ranks = [e["rank"] for e in entries]
        assert ranks == [1, 2]
