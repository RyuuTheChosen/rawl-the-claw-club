"""Integration tests for GET /api/gateway/fighters and recalibrate."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from rawl.db.models.fighter import Fighter


class TestListMyFighters:
    async def test_list_my_fighters(self, client, seed_fighters, api_key_header):
        """Returns only fighters owned by the authenticated user."""
        r = await client.get("/api/gateway/fighters", headers=api_key_header)
        assert r.status_code == 200
        data = r.json()
        # seed_user owns ReadyBot + ValidatingBot = 2
        assert len(data) == 2
        names = {f["name"] for f in data}
        assert "ReadyBot" in names
        assert "ValidatingBot" in names


class TestGetMyFighter:
    async def test_get_my_fighter_not_owned(
        self, client, seed_fighters, api_key_header
    ):
        """User A cannot see user B's fighter via gateway."""
        opponent = seed_fighters[2]  # owned by user B
        r = await client.get(
            f"/api/gateway/fighters/{opponent.id}", headers=api_key_header
        )
        assert r.status_code == 404


class TestRecalibrate:
    async def test_recalibrate_success(
        self, client, db_session, seed_fighters, api_key_header
    ):
        """Fighter in calibration_failed → can recalibrate."""
        fighter = seed_fighters[0]
        fighter.status = "calibration_failed"
        await db_session.flush()

        with patch(
            "rawl.engine.emulation_queue.enqueue_calibration_now", new_callable=AsyncMock
        ):
            r = await client.post(
                f"/api/gateway/fighters/{fighter.id}/recalibrate",
                headers=api_key_header,
            )
        assert r.status_code == 200
        assert "Recalibration started" in r.json()["message"]

    async def test_recalibrate_wrong_status(
        self, client, seed_fighters, api_key_header
    ):
        """Fighter in ready status cannot recalibrate."""
        fighter = seed_fighters[0]  # status = ready
        r = await client.post(
            f"/api/gateway/fighters/{fighter.id}/recalibrate",
            headers=api_key_header,
        )
        assert r.status_code == 400
