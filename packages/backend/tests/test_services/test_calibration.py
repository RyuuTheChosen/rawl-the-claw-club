"""Unit tests for calibration flow in rawl.services.elo.run_calibration."""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rawl.services.elo import calculate_new_rating, get_division


# Minimal stand-in for MatchResult
@dataclass
class FakeMatchResult:
    match_id: str
    winner: str
    match_hash: str
    round_history: list
    adapter_version: str = "1.0.0"
    hash_version: int = 2
    hash_payload: bytes = b""


def _make_fighter(**overrides):
    """Create a mock Fighter with sensible defaults."""
    fighter = MagicMock()
    fighter.id = overrides.get("id", uuid.uuid4())
    fighter.game_id = overrides.get("game_id", "sfiii3n")
    fighter.model_path = overrides.get("model_path", "models/test.zip")
    fighter.elo_rating = overrides.get("elo_rating", 1200.0)
    fighter.matches_played = overrides.get("matches_played", 0)
    fighter.wins = overrides.get("wins", 0)
    fighter.losses = overrides.get("losses", 0)
    fighter.status = overrides.get("status", "calibrating")
    fighter.division_tier = overrides.get("division_tier", "Silver")
    return fighter


def _make_db(fighter):
    """Create a mock async DB session that returns the fighter."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fighter
    result_mock.scalars.return_value.all.return_value = [fighter]
    db.execute.return_value = result_mock
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


SETTINGS_DEFAULTS = {
    "calibration_reference_elo_list": [1000, 1100, 1200, 1400, 1600],
    "calibration_min_success": 3,
    "calibration_max_retries": 2,
    "default_match_format": 3,
    "elo_rating_floor": 800.0,
    "elo_calibration_match_threshold": 10,
    "elo_k_calibration": 40,
    "elo_k_established": 20,
    "elo_k_elite": 16,
    "elo_elite_threshold": 1800.0,
}


def _mock_settings(**overrides):
    """Create a mock settings object with defaults."""
    s = MagicMock()
    vals = {**SETTINGS_DEFAULTS, **overrides}
    for k, v in vals.items():
        setattr(s, k, v)
    return s


@pytest.fixture
def fighter():
    return _make_fighter()


@pytest.fixture
def db(fighter):
    return _make_db(fighter)


@pytest.fixture(autouse=True)
def mock_match_runner_module():
    """Inject a mock for rawl.engine.match_runner into sys.modules.

    This avoids importing the real module which has heavy dependencies
    (stable-retro, Redis, S3, etc.) not available in unit tests.
    """
    mock_module = MagicMock()
    mock_module.run_match = AsyncMock()
    saved = sys.modules.get("rawl.engine.match_runner")
    sys.modules["rawl.engine.match_runner"] = mock_module
    yield mock_module
    if saved is not None:
        sys.modules["rawl.engine.match_runner"] = saved
    else:
        sys.modules.pop("rawl.engine.match_runner", None)


# ── Calibration success path ────────────────────────────────────

@pytest.mark.asyncio
async def test_calibration_all_wins(fighter, db, mock_match_runner_module):
    """All 5 calibration matches won -> status=ready."""
    wins = []

    async def mock_run_match(*args, **kwargs):
        wins.append(kwargs["match_id"])
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner="P1",
            match_hash="abc123",
            round_history=[{"winner": "P1"}],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        result = await run_calibration(str(fighter.id), db)

    assert result is True
    assert fighter.status == "ready"
    assert len(wins) == 5
    assert fighter.elo_rating > 1200.0
    assert fighter.division_tier == get_division(fighter.elo_rating)


@pytest.mark.asyncio
async def test_calibration_mixed_results(fighter, db, mock_match_runner_module):
    """3 wins 2 losses -> still passes (min_success=3)."""
    call_count = 0

    async def mock_run_match(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        winner = "P1" if call_count <= 3 else "P2"
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner=winner,
            match_hash="hash123",
            round_history=[{"winner": winner}],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        result = await run_calibration(str(fighter.id), db)

    assert result is True
    assert fighter.status == "ready"


# ── Calibration failure path ────────────────────────────────────

@pytest.mark.asyncio
async def test_calibration_too_many_errors(fighter, db, mock_match_runner_module):
    """All matches error -> status=calibration_failed."""
    async def mock_run_match(*args, **kwargs):
        raise RuntimeError("Emulation engine crashed")

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        result = await run_calibration(str(fighter.id), db)

    assert result is False
    assert fighter.status == "calibration_failed"
    assert fighter.elo_rating == 1200.0


@pytest.mark.asyncio
async def test_calibration_fighter_not_found(db, mock_match_runner_module):
    """Non-existent fighter -> returns False immediately."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        result = await run_calibration("nonexistent-id", db)

    assert result is False


# ── Sequential Elo tracking ─────────────────────────────────────

@pytest.mark.asyncio
async def test_calibration_sequential_elo(fighter, db, mock_match_runner_module):
    """Elo is updated after each calibration match, not batch."""
    elo_snapshots = []

    async def mock_run_match(*args, **kwargs):
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner="P1",
            match_hash="hash",
            round_history=[],
        )

    mock_match_runner_module.run_match = mock_run_match

    original_calc = calculate_new_rating

    def tracking_calc(rating, opp_rating, won, matches_played):
        elo_snapshots.append(rating)
        return original_calc(rating, opp_rating, won, matches_played)

    with patch("rawl.services.elo.calculate_new_rating", side_effect=tracking_calc), \
         patch("rawl.services.elo.settings", _mock_settings(
             calibration_reference_elo_list=[1000, 1100, 1200],
             calibration_min_success=2,
             calibration_max_retries=1,
         )):
        from rawl.services.elo import run_calibration
        await run_calibration(str(fighter.id), db)

    assert len(elo_snapshots) == 3
    assert elo_snapshots[0] == 1200.0
    assert elo_snapshots[1] > elo_snapshots[0]
    assert elo_snapshots[2] > elo_snapshots[1]


# ── Retry on error then succeed ─────────────────────────────────

@pytest.mark.asyncio
async def test_calibration_retry_then_succeed(fighter, db, mock_match_runner_module):
    """First attempt errors, second attempt succeeds."""
    call_count = 0

    async def mock_run_match(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Transient error")
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner="P1",
            match_hash="hash",
            round_history=[],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings(
             calibration_reference_elo_list=[1000],
             calibration_min_success=1,
         )):
        from rawl.services.elo import run_calibration
        result = await run_calibration(str(fighter.id), db)

    assert result is True
    assert fighter.status == "ready"


# ── run_match returns None ──────────────────────────────────────

@pytest.mark.asyncio
async def test_calibration_run_match_returns_none(fighter, db, mock_match_runner_module):
    """run_match returning None is treated as an error."""
    async def mock_run_match(*args, **kwargs):
        return None

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        result = await run_calibration(str(fighter.id), db)

    assert result is False
    assert fighter.status == "calibration_failed"


# ── calibration=True passed to run_match ──────────────────────

@pytest.mark.asyncio
async def test_calibration_passes_calibration_flag(fighter, db, mock_match_runner_module):
    """run_match() must be called with calibration=True."""
    captured_kwargs = []

    async def mock_run_match(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner="P1",
            match_hash="hash",
            round_history=[],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings(
             calibration_reference_elo_list=[1000],
             calibration_min_success=1,
             calibration_max_retries=1,
         )):
        from rawl.services.elo import run_calibration
        await run_calibration(str(fighter.id), db)

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["calibration"] is True


# ── matches_played / wins / losses updated ────────────────────

@pytest.mark.asyncio
async def test_calibration_updates_match_stats_all_wins(fighter, db, mock_match_runner_module):
    """All 5 wins -> matches_played=5, wins=5, losses=0."""
    async def mock_run_match(*args, **kwargs):
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner="P1",
            match_hash="hash",
            round_history=[],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        await run_calibration(str(fighter.id), db)

    assert fighter.matches_played == 5
    assert fighter.wins == 5
    assert fighter.losses == 0


@pytest.mark.asyncio
async def test_calibration_updates_match_stats_mixed(fighter, db, mock_match_runner_module):
    """3 wins, 2 losses -> matches_played=5, wins=3, losses=2."""
    call_count = 0

    async def mock_run_match(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        winner = "P1" if call_count <= 3 else "P2"
        return FakeMatchResult(
            match_id=kwargs["match_id"],
            winner=winner,
            match_hash="hash",
            round_history=[],
        )

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        await run_calibration(str(fighter.id), db)

    assert fighter.matches_played == 5
    assert fighter.wins == 3
    assert fighter.losses == 2


@pytest.mark.asyncio
async def test_calibration_stats_zero_on_all_errors(fighter, db, mock_match_runner_module):
    """All errors -> matches_played=0, wins=0, losses=0."""
    async def mock_run_match(*args, **kwargs):
        raise RuntimeError("engine crash")

    mock_match_runner_module.run_match = mock_run_match

    with patch("rawl.services.elo.settings", _mock_settings()):
        from rawl.services.elo import run_calibration
        await run_calibration(str(fighter.id), db)

    assert fighter.matches_played == 0
    assert fighter.wins == 0
    assert fighter.losses == 0
    assert fighter.status == "calibration_failed"
