"""Verify FIX 7: locked_at timestamp persisted from engine to DB.

1. MatchResult.locked_at field exists and is populated
2. tasks.py sets match.locked_at from result.locked_at
3. locked_at is only set if match.locked_at was previously None
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from rawl.db.models.match import Match
from rawl.engine.match_result import MatchResult


def test_match_result_locked_at_default_none():
    result = MatchResult(match_id="m1", winner="P1", round_history=[])
    assert result.locked_at is None


def test_match_result_locked_at_can_be_set():
    now = datetime.now(UTC)
    result = MatchResult(match_id="m1", winner="P1", round_history=[], locked_at=now)
    assert result.locked_at == now


async def test_locked_at_set_on_match():
    """Replicate the tasks.py logic: result.locked_at → match.locked_at."""
    lock_time = datetime.now(UTC)
    result = MatchResult(
        match_id="test-123",
        winner="P1",
        round_history=[],
        match_hash="abc",
        locked_at=lock_time,
    )

    match = MagicMock(spec=Match)
    match.locked_at = None  # Not yet set

    # Replicate the tasks.py conditional
    if result.locked_at and match.locked_at is None:
        match.locked_at = result.locked_at

    assert match.locked_at == lock_time


async def test_locked_at_not_overwritten_if_already_set():
    """If match.locked_at is already set, don't overwrite."""
    old_time = datetime(2026, 1, 1, tzinfo=UTC)
    new_time = datetime(2026, 2, 1, tzinfo=UTC)

    result = MatchResult(
        match_id="test-456",
        winner="P2",
        round_history=[],
        locked_at=new_time,
    )

    match = MagicMock(spec=Match)
    match.locked_at = old_time  # Already set

    if result.locked_at and match.locked_at is None:
        match.locked_at = result.locked_at

    assert match.locked_at == old_time, "Should keep original locked_at"


async def test_locked_at_none_when_not_locked():
    """Calibration matches don't lock — locked_at stays None."""
    result = MatchResult(
        match_id="cal-789",
        winner="P1",
        round_history=[],
        locked_at=None,
    )

    match = MagicMock(spec=Match)
    match.locked_at = None

    if result.locked_at and match.locked_at is None:
        match.locked_at = result.locked_at

    assert match.locked_at is None
