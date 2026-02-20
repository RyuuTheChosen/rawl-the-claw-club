"""Integration tests for GET/POST /api/matches."""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import make_internal_token


class TestListMatches:
    async def test_list_matches_empty(self, client):
        r = await client.get("/api/matches")
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["has_more"] is False

    async def test_list_matches_returns_seeded(self, client, seed_matches):
        r = await client.get("/api/matches")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    async def test_list_matches_pagination_limit(self, client, seed_matches):
        """Limit param correctly restricts result count."""
        r1 = await client.get("/api/matches", params={"limit": 2})
        body1 = r1.json()
        assert len(body1["items"]) == 2
        assert body1["has_more"] is True

    async def test_list_matches_pagination_cursor(self, client, seed_matches):
        """Cursor is returned and following it yields results."""
        r1 = await client.get("/api/matches", params={"limit": 2})
        body1 = r1.json()
        assert body1["next_cursor"] is not None
        # Following the cursor should return a valid response
        r2 = await client.get(
            "/api/matches",
            params={"limit": 10, "cursor": body1["next_cursor"]},
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert isinstance(body2["items"], list)
        assert len(body2["items"]) >= 1

    async def test_list_matches_filter_status_upcoming(self, client, seed_matches):
        r = await client.get("/api/matches", params={"status": "upcoming"})
        items = r.json()["items"]
        assert all(m["status"] == "open" for m in items)
        assert len(items) == 1

    async def test_list_matches_filter_status_live(self, client, seed_matches):
        r = await client.get("/api/matches", params={"status": "live"})
        items = r.json()["items"]
        assert all(m["status"] == "locked" for m in items)
        assert len(items) == 1

    async def test_list_matches_filter_status_completed(self, client, seed_matches):
        r = await client.get("/api/matches", params={"status": "completed"})
        items = r.json()["items"]
        assert all(m["status"] == "resolved" for m in items)
        assert len(items) == 1

    async def test_list_matches_filter_game(self, client, seed_matches):
        r = await client.get("/api/matches", params={"game": "sf2ce"})
        assert len(r.json()["items"]) == 3

        r2 = await client.get("/api/matches", params={"game": "nonexistent"})
        assert len(r2.json()["items"]) == 0


class TestGetMatch:
    async def test_get_match_found(self, client, seed_matches):
        match_id = str(seed_matches[0].id)
        r = await client.get(f"/api/matches/{match_id}")
        assert r.status_code == 200
        assert r.json()["id"] == match_id

    async def test_get_match_not_found(self, client):
        r = await client.get(f"/api/matches/{uuid.uuid4()}")
        assert r.status_code == 404


class TestCreateMatch:
    async def test_create_match_with_internal_auth(
        self, client, seed_fighters, internal_token_header
    ):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
            "match_format": 3,
        }
        r = await client.post("/api/matches", json=body, headers=internal_token_header)
        assert r.status_code == 201
        data = r.json()
        assert data["game_id"] == "sf2ce"
        assert data["status"] == "open"

    async def test_create_match_missing_auth(self, client, seed_fighters):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post("/api/matches", json=body)
        assert r.status_code == 401

    async def test_create_match_expired_token(
        self, client, seed_fighters, expired_token_header
    ):
        fa, _, fb, _ = seed_fighters
        body = {
            "game_id": "sf2ce",
            "fighter_a_id": str(fa.id),
            "fighter_b_id": str(fb.id),
        }
        r = await client.post("/api/matches", json=body, headers=expired_token_header)
        assert r.status_code == 401
