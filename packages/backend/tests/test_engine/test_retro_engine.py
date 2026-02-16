from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rawl.engine.emulation.retro_engine import RetroEngine


@pytest.fixture
def engine():
    return RetroEngine(game_id="sf2ce", match_id="test-match-001")


@pytest.fixture
def mock_retro():
    """Inject a mock ``retro`` module into sys.modules.

    retro_engine.py imports ``retro`` lazily inside start(), so we
    need to place the mock in sys.modules before start() runs.
    """
    mock_mod = MagicMock()
    mock_mod.Actions.FILTERED = "FILTERED"
    mock_mod.data.Integrations.ALL = "ALL"
    saved = sys.modules.get("retro")
    sys.modules["retro"] = mock_mod
    yield mock_mod
    if saved is None:
        sys.modules.pop("retro", None)
    else:
        sys.modules["retro"] = saved


# ------------------------------------------------------------------
# Observation translation
# ------------------------------------------------------------------

class TestTranslateObs:
    def test_resize_and_wrap(self, engine):
        raw = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine._translate_obs(raw)

        assert "P1" in result and "P2" in result
        assert result["P1"].shape == (256, 256, 3)
        assert result["P2"].shape == (256, 256, 3)

    def test_p1_and_p2_share_same_frame(self, engine):
        raw = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = engine._translate_obs(raw)
        np.testing.assert_array_equal(result["P1"], result["P2"])

    def test_custom_obs_size(self):
        eng = RetroEngine(game_id="sf2ce", match_id="test")
        eng._obs_size = 128
        raw = np.zeros((480, 640, 3), dtype=np.uint8)
        result = eng._translate_obs(raw)
        assert result["P1"].shape == (128, 128, 3)


# ------------------------------------------------------------------
# Info translation — SF2 Genesis format
# ------------------------------------------------------------------

class TestTranslateInfoSF2:
    def test_basic_nesting(self, engine):
        raw_info = {
            "health": 176,
            "enemy_health": 80,
            "continuetimer": 55,
        }
        info = engine._translate_info(raw_info)

        assert info["P1"]["health"] == 176
        assert info["P2"]["health"] == 80
        assert info["timer"] == 55

    def test_round_wins(self, engine):
        raw_info = {
            "health": 100,
            "enemy_health": 50,
            "continuetimer": 40,
            "matches_won": 1,
            "enemy_matches_won": 0,
        }
        info = engine._translate_info(raw_info)

        assert info["P1"]["round_wins"] == 1
        assert info["P2"]["round_wins"] == 0
        assert info["round"] == 2  # 1 + 0 + 1

    def test_defaults_for_missing_fields(self, engine):
        raw_info = {
            "health": 176,
            "enemy_health": 176,
            "continuetimer": 99,
        }
        info = engine._translate_info(raw_info)

        assert info["P1"]["stage_side"] == 0
        assert info["P1"]["combo_count"] == 0
        assert info["P2"]["stage_side"] == 0
        assert info["P2"]["combo_count"] == 0

    def test_extra_keys_passed_through(self, engine):
        raw_info = {
            "health": 176,
            "enemy_health": 176,
            "continuetimer": 99,
            "score": 50000,
        }
        info = engine._translate_info(raw_info)
        assert info["score"] == 50000

    def test_round_defaults_to_1_when_no_wins(self, engine):
        raw_info = {
            "health": 176,
            "enemy_health": 176,
            "continuetimer": 99,
        }
        info = engine._translate_info(raw_info)
        assert info["round"] == 1  # 0 + 0 + 1


# ------------------------------------------------------------------
# Info translation — prefixed format (backward compat)
# ------------------------------------------------------------------

class TestTranslateInfoPrefixed:
    def test_basic_nesting(self, engine):
        raw_info = {
            "p1_health": 160,
            "p2_health": 80,
            "time": 55,
        }
        info = engine._translate_info(raw_info)

        assert info["P1"]["health"] == 160
        assert info["P2"]["health"] == 80
        assert info["timer"] == 55

    def test_round_wins_to_round(self, engine):
        raw_info = {
            "p1_health": 100,
            "p2_health": 50,
            "time": 40,
            "p1_round_wins": 1,
            "p2_round_wins": 0,
        }
        info = engine._translate_info(raw_info)

        assert info["P1"]["round_wins"] == 1
        assert info["P2"]["round_wins"] == 0
        assert info["round"] == 2

    def test_stage_side_preserved(self, engine):
        raw_info = {
            "p1_health": 160,
            "p2_health": 160,
            "time": 99,
            "p1_stage_side": 1,
            "p2_stage_side": -1,
        }
        info = engine._translate_info(raw_info)
        assert info["P1"]["stage_side"] == 1
        assert info["P2"]["stage_side"] == -1

    def test_unknown_globals_stay_top_level(self, engine):
        raw_info = {
            "p1_health": 160,
            "p2_health": 160,
            "time": 99,
            "fighting_status": 2,
        }
        info = engine._translate_info(raw_info)
        assert info["fighting_status"] == 2


# ------------------------------------------------------------------
# Action translation
# ------------------------------------------------------------------

class TestTranslateAction:
    def test_concatenation(self, engine):
        action = {
            "P1": np.array([1, 0, 3]),
            "P2": np.array([2, 1, 0]),
        }
        flat = engine._translate_action(action)
        np.testing.assert_array_equal(flat, np.array([1, 0, 3, 2, 1, 0]))

    def test_preserves_dtype(self, engine):
        action = {
            "P1": np.array([1, 0, 3], dtype=np.int64),
            "P2": np.array([2, 1, 0], dtype=np.int64),
        }
        flat = engine._translate_action(action)
        assert flat.dtype == np.int64


# ------------------------------------------------------------------
# Adapter compatibility
# ------------------------------------------------------------------

class TestAdapterCompatibility:
    def test_translated_info_passes_sf2ce_validate(self, engine):
        """Ensure translated SF2 info has all fields the sf2ce adapter requires."""
        from rawl.game_adapters.sf2ce import SF2CEAdapter

        raw_info = {
            "health": 176,
            "enemy_health": 176,
            "continuetimer": 99,
            "matches_won": 0,
            "enemy_matches_won": 0,
        }
        info = engine._translate_info(raw_info)

        adapter = SF2CEAdapter()
        adapter.validate_info(info)

    def test_translated_info_extract_state(self, engine):
        from rawl.game_adapters.sf2ce import SF2CEAdapter

        raw_info = {
            "health": 120,
            "enemy_health": 80,
            "continuetimer": 45,
            "matches_won": 1,
            "enemy_matches_won": 0,
        }
        info = engine._translate_info(raw_info)

        adapter = SF2CEAdapter()
        state = adapter.extract_state(info)

        assert state.p1_health == pytest.approx(120 / 176)
        assert state.p2_health == pytest.approx(80 / 176)
        assert state.timer == 45
        assert state.round_number == 2
        assert state.stage_side == 0


# ------------------------------------------------------------------
# Start / step / stop with mocked retro
# ------------------------------------------------------------------

class TestLifecycle:
    def test_start_creates_env_and_returns_translated(self, engine, mock_retro):
        mock_env = MagicMock()
        mock_env.reset.return_value = (
            np.zeros((200, 256, 3), dtype=np.uint8),
            {"health": 176, "enemy_health": 176, "continuetimer": 99},
        )
        mock_retro.make.return_value = mock_env

        obs, info = engine.start()

        mock_retro.make.assert_called_once()
        assert "P1" in obs and "P2" in obs
        assert obs["P1"].shape == (256, 256, 3)
        assert info["P1"]["health"] == 176
        assert info["timer"] == 99

    def test_start_uses_filtered_actions(self, engine, mock_retro):
        mock_env = MagicMock()
        mock_env.reset.return_value = (
            np.zeros((200, 256, 3), dtype=np.uint8),
            {"health": 176, "enemy_health": 176, "continuetimer": 99},
        )
        mock_retro.make.return_value = mock_env

        engine.start()

        call_kwargs = mock_retro.make.call_args
        assert call_kwargs[1]["use_restricted_actions"] == "FILTERED"

    def test_step_translates_round_trip(self, engine, mock_retro):
        mock_env = MagicMock()
        mock_env.reset.return_value = (
            np.zeros((200, 256, 3), dtype=np.uint8),
            {"health": 176, "enemy_health": 176, "continuetimer": 99},
        )
        mock_env.step.return_value = (
            np.zeros((200, 256, 3), dtype=np.uint8),
            0.0,
            False,
            False,
            {"health": 140, "enemy_health": 176, "continuetimer": 98},
        )
        mock_retro.make.return_value = mock_env

        engine.start()
        obs, reward, term, trunc, info = engine.step(
            {"P1": np.array([1, 0, 3]), "P2": np.array([0, 2, 1])}
        )

        assert info["P1"]["health"] == 140
        assert info["P2"]["health"] == 176
        assert info["timer"] == 98

        call_args = mock_env.step.call_args[0][0]
        np.testing.assert_array_equal(call_args, np.array([1, 0, 3, 0, 2, 1]))

    def test_step_before_start_raises(self, engine):
        with pytest.raises(RuntimeError, match="not started"):
            engine.step({"P1": np.array([0, 0, 0]), "P2": np.array([0, 0, 0])})

    def test_stop_closes_env(self, engine, mock_retro):
        mock_env = MagicMock()
        mock_env.reset.return_value = (
            np.zeros((200, 256, 3), dtype=np.uint8),
            {"health": 176, "enemy_health": 176, "continuetimer": 99},
        )
        mock_retro.make.return_value = mock_env

        engine.start()
        engine.stop()

        mock_env.close.assert_called_once()
        assert engine._env is None

    def test_stop_without_start_is_noop(self, engine):
        engine.stop()
