"""Integration tests for rawl.services.match_queue."""
from __future__ import annotations

import uuid

import pytest

from rawl.services.match_queue import (
    enqueue_fighter,
    dequeue_fighter,
    get_active_game_ids,
    try_match,
    widen_windows,
)


class TestEnqueueDequeue:
    async def test_enqueue_and_dequeue(self):
        fid = uuid.uuid4()
        await enqueue_fighter(fid, "sf2ce", "ranked", 1200.0, "owner1")
        ids = await get_active_game_ids()
        assert "sf2ce" in ids

        await dequeue_fighter(fid, "sf2ce")


class TestTryMatch:
    async def test_try_match_pair_found(self):
        """Two fighters within Elo window → matched."""
        fid_a = uuid.uuid4()
        fid_b = uuid.uuid4()
        await enqueue_fighter(fid_a, "sf2ce", "ranked", 1200.0, "owner_a")
        await enqueue_fighter(fid_b, "sf2ce", "ranked", 1300.0, "owner_b")

        result = await try_match("sf2ce")
        assert result is not None
        ids = {result[0], result[1]}
        assert str(fid_a) in ids
        assert str(fid_b) in ids

    async def test_try_match_self_matching_blocked(self):
        """Same owner → no match."""
        fid_a = uuid.uuid4()
        fid_b = uuid.uuid4()
        await enqueue_fighter(fid_a, "sf2ce", "ranked", 1200.0, "same_owner")
        await enqueue_fighter(fid_b, "sf2ce", "ranked", 1200.0, "same_owner")

        result = await try_match("sf2ce")
        assert result is None

        # Cleanup
        await dequeue_fighter(fid_a, "sf2ce")
        await dequeue_fighter(fid_b, "sf2ce")

    async def test_try_match_no_pair_elo_gap(self):
        """Elo gap too wide (>200 base) → no match on first tick."""
        fid_a = uuid.uuid4()
        fid_b = uuid.uuid4()
        await enqueue_fighter(fid_a, "sf2ce", "ranked", 1000.0, "owner_a")
        await enqueue_fighter(fid_b, "sf2ce", "ranked", 1500.0, "owner_b")

        result = await try_match("sf2ce")
        # 500 gap > 200 base window → no match
        assert result is None

        await dequeue_fighter(fid_a, "sf2ce")
        await dequeue_fighter(fid_b, "sf2ce")


class TestWidenWindows:
    async def test_widen_windows(self):
        fid = uuid.uuid4()
        await enqueue_fighter(fid, "sf2ce", "ranked", 1200.0, "owner_x")
        await widen_windows("sf2ce")
        # Should not error; just increments ticks
        await dequeue_fighter(fid, "sf2ce")
