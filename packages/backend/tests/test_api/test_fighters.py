"""Integration tests for GET /api/fighters."""
from __future__ import annotations

import uuid

import pytest


class TestListFighters:
    async def test_list_fighters_only_ready(self, client, seed_fighters):
        r = await client.get("/api/fighters")
        assert r.status_code == 200
        items = r.json()["items"]
        # seed_fighters has 3 ready + 1 validating; only ready returned
        assert all(f["status"] == "ready" for f in items)
        assert len(items) == 3

    async def test_list_fighters_sorted_by_elo(self, client, seed_fighters):
        r = await client.get("/api/fighters")
        items = r.json()["items"]
        elos = [f["elo_rating"] for f in items]
        assert elos == sorted(elos, reverse=True)

    async def test_list_fighters_filter_game(self, client, seed_fighters):
        r = await client.get("/api/fighters", params={"game": "sf2ce"})
        items = r.json()["items"]
        assert all(f["game_id"] == "sf2ce" for f in items)
        assert len(items) == 2  # ReadyBot (1400) + OpponentBot (1300)

    async def test_list_fighters_limit(self, client, seed_fighters):
        r = await client.get("/api/fighters", params={"limit": 1})
        assert len(r.json()["items"]) == 1


class TestGetFighter:
    async def test_get_fighter_found(self, client, seed_fighters):
        fid = str(seed_fighters[0].id)
        r = await client.get(f"/api/fighters/{fid}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == fid
        assert data["name"] == "ReadyBot"

    async def test_get_fighter_not_found(self, client):
        r = await client.get(f"/api/fighters/{uuid.uuid4()}")
        assert r.status_code == 404
