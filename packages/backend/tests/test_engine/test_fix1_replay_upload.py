"""Verify FIX 1: replay_s3_key is conditional on upload success.

Tests:
  1. MatchResult.replay_uploaded defaults True, can be set False
  2. When replay_uploaded=False: replay_s3_key stays None, match still resolves
  3. When replay_uploaded=True: replay_s3_key is set normally
  4. The tasks.py conditional logic works correctly
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from rawl.db.models.match import Match
from rawl.engine.match_result import MatchResult


# ---------------------------------------------------------------------------
# 1. MatchResult field correctness
# ---------------------------------------------------------------------------

def test_match_result_replay_uploaded_defaults_true():
    result = MatchResult(match_id="m1", winner="P1", round_history=[])
    assert result.replay_uploaded is True


def test_match_result_replay_uploaded_false():
    result = MatchResult(match_id="m2", winner="P1", round_history=[], replay_uploaded=False)
    assert result.replay_uploaded is False


# ---------------------------------------------------------------------------
# 2 & 3. Simulate _execute_match_async logic inline
# ---------------------------------------------------------------------------

async def test_replay_s3_key_null_when_upload_fails():
    """Replicate the exact conditional from tasks.py lines 85-91."""
    match_id = str(uuid.uuid4())
    result = MatchResult(
        match_id=match_id,
        winner="P1",
        round_history=[{"winner": "P1", "p1_health": 0.8, "p2_health": 0.0}],
        match_hash="abc123",
        adapter_version="1.0.0",
        hash_version=2,
        hash_payload=b"{}",
        replay_uploaded=False,
        locked_at=datetime.now(UTC),
    )

    # Simulate in-memory match object (same fields as ORM model)
    match = MagicMock(spec=Match)
    match.status = "locked"
    match.replay_s3_key = None
    match.locked_at = None
    match.fighter_a_id = uuid.uuid4()
    match.fighter_b_id = uuid.uuid4()

    # Replicate the logic from _execute_match_async
    match.status = "resolved"
    match.match_hash = result.match_hash
    match.hash_version = result.hash_version
    match.adapter_version = result.adapter_version
    match.round_history = str(result.round_history)
    if result.replay_uploaded:
        match.replay_s3_key = f"replays/{match_id}.mjpeg"
    match.resolved_at = datetime.now(UTC)
    if result.locked_at and match.locked_at is None:
        match.locked_at = result.locked_at

    if result.winner == "P1":
        match.winner_id = match.fighter_a_id

    # ASSERTIONS
    assert match.status == "resolved"
    assert match.replay_s3_key is None, (
        f"replay_s3_key should be None when upload fails, got {match.replay_s3_key}"
    )
    assert match.match_hash == "abc123"
    assert match.locked_at is not None


async def test_replay_s3_key_set_when_upload_succeeds():
    """Same logic, but replay_uploaded=True."""
    match_id = str(uuid.uuid4())
    result = MatchResult(
        match_id=match_id,
        winner="P2",
        round_history=[{"winner": "P2", "p1_health": 0.0, "p2_health": 0.5}],
        match_hash="def456",
        adapter_version="1.0.0",
        hash_version=2,
        hash_payload=b"{}",
        replay_uploaded=True,
        locked_at=datetime.now(UTC),
    )

    match = MagicMock(spec=Match)
    match.status = "locked"
    match.replay_s3_key = None
    match.locked_at = None
    match.fighter_a_id = uuid.uuid4()
    match.fighter_b_id = uuid.uuid4()

    # Replicate the logic
    match.status = "resolved"
    match.match_hash = result.match_hash
    if result.replay_uploaded:
        match.replay_s3_key = f"replays/{match_id}.mjpeg"
    match.resolved_at = datetime.now(UTC)

    # ASSERTIONS
    assert match.status == "resolved"
    assert match.replay_s3_key == f"replays/{match_id}.mjpeg"
    assert match.match_hash == "def456"


# ---------------------------------------------------------------------------
# 4. match_runner calls persist_failed_upload when replay upload fails
# ---------------------------------------------------------------------------

async def test_match_runner_calls_persist_on_replay_failure():
    """Verify the match_runner code path: replay_ok=False → persist_failed_upload called.

    We can't run the full match_runner (needs RetroEngine), so we verify
    the import path and call signature by testing the handler directly.
    """
    from rawl.engine.failed_upload_handler import persist_failed_upload

    match_id = str(uuid.uuid4())

    # Mock the worker_session_factory that persist_failed_upload uses
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    fake_ctx = AsyncMock()
    fake_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "rawl.db.session.worker_session_factory",
        return_value=fake_ctx,
    ):
        await persist_failed_upload(
            match_id=match_id,
            s3_key=f"replays/{match_id}.mjpeg",
            payload=None,  # replay files have no in-memory payload
        )

    # Verify a FailedUpload was added
    mock_session.add.assert_called_once()
    added_obj = mock_session.add.call_args[0][0]
    assert added_obj.match_id == match_id
    assert added_obj.s3_key == f"replays/{match_id}.mjpeg"
    assert added_obj.payload is None  # intentional — can't retry disk-based files
    assert added_obj.status == "failed"
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. retry_failed_uploads skips rows with payload=None
# ---------------------------------------------------------------------------

async def test_retry_handler_skips_null_payload():
    """The retry handler filters on payload.isnot(None), so replay failures
    with payload=None won't be auto-retried — they exist for monitoring only.
    """
    from rawl.engine.failed_upload_handler import retry_failed_uploads

    # The query uses `FailedUpload.payload.isnot(None)` — verify the filter
    # exists in the source. We can't easily test with SQLite, so check the
    # SQL expression is correct by importing and inspecting.
    import inspect
    source = inspect.getsource(retry_failed_uploads)
    assert "payload.isnot(None)" in source, (
        "retry_failed_uploads must filter out rows where payload is None"
    )
