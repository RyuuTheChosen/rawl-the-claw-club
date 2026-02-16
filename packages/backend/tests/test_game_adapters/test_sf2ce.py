import pytest

from rawl.game_adapters.sf2ce import SF2CEAdapter
from rawl.game_adapters.errors import AdapterValidationError


@pytest.fixture
def adapter():
    return SF2CEAdapter()


def _make_info(p1_health=176, p2_health=176, p1_round_wins=0, p2_round_wins=0, round_num=1):
    return {
        "P1": {
            "health": p1_health, "round_wins": p1_round_wins,
            "round": round_num, "timer": 0, "stage_side": 0, "combo_count": 0,
        },
        "P2": {
            "health": p2_health, "round_wins": p2_round_wins,
            "round": round_num, "timer": 0, "stage_side": 0, "combo_count": 0,
        },
        "round": round_num,
        "timer": 0,
    }


class TestValidation:
    def test_valid_info(self, adapter):
        info = _make_info()
        adapter.validate_info(info)

    def test_missing_health(self, adapter):
        info = {
            "P1": {"round_wins": 0},
            "P2": {"round_wins": 0},
        }
        with pytest.raises(AdapterValidationError) as exc_info:
            adapter.validate_info(info)
        assert "health" in str(exc_info.value)

    def test_missing_round_wins(self, adapter):
        info = {
            "P1": {"health": 176},
            "P2": {"health": 176},
        }
        with pytest.raises(AdapterValidationError) as exc_info:
            adapter.validate_info(info)
        assert "round_wins" in str(exc_info.value)

    def test_missing_player(self, adapter):
        info = {"P1": {"health": 176, "round_wins": 0}}
        with pytest.raises(AdapterValidationError) as exc_info:
            adapter.validate_info(info)
        assert "P2" in str(exc_info.value)


class TestExtractState:
    def test_full_health(self, adapter):
        state = adapter.extract_state(_make_info())
        assert state.p1_health == pytest.approx(1.0)
        assert state.p2_health == pytest.approx(1.0)

    def test_zero_health(self, adapter):
        state = adapter.extract_state(_make_info(p1_health=0))
        assert state.p1_health == pytest.approx(0.0)

    def test_negative_health_clamped(self, adapter):
        state = adapter.extract_state(_make_info(p1_health=-10))
        assert state.p1_health == pytest.approx(0.0)

    def test_max_health(self, adapter):
        state = adapter.extract_state(_make_info(p1_health=176))
        assert state.p1_health == pytest.approx(1.0)

    def test_half_health(self, adapter):
        state = adapter.extract_state(_make_info(p1_health=88))
        assert state.p1_health == pytest.approx(88 / 176)

    def test_timer_always_zero(self, adapter):
        """SF2 Genesis continuetimer is always 0 during gameplay."""
        state = adapter.extract_state(_make_info())
        assert state.timer == 0

    def test_round_number(self, adapter):
        state = adapter.extract_state(_make_info(round_num=3))
        assert state.round_number == 3


class TestIsRoundOver:
    """Round detection uses matches_won delta — NOT health checks."""

    def test_no_change_not_over(self, adapter):
        """Both round_wins at 0, no change from init → not over."""
        assert adapter.is_round_over(_make_info()) is False

    def test_p1_wins_round(self, adapter):
        """P1 round_wins goes 0→1 → detected exactly once."""
        result = adapter.is_round_over(_make_info(p1_round_wins=1))
        assert result == "P1"

    def test_p1_win_not_repeated(self, adapter):
        """Same round_wins=1 on next frame → no duplicate detection."""
        adapter.is_round_over(_make_info(p1_round_wins=1))  # first detection
        result = adapter.is_round_over(_make_info(p1_round_wins=1))  # same frame
        assert result is False

    def test_p2_wins_round(self, adapter):
        result = adapter.is_round_over(_make_info(p2_round_wins=1))
        assert result == "P2"

    def test_p2_win_not_repeated(self, adapter):
        adapter.is_round_over(_make_info(p2_round_wins=1))
        result = adapter.is_round_over(_make_info(p2_round_wins=1))
        assert result is False

    def test_sequential_rounds(self, adapter):
        """P1 wins round 1, P2 wins round 2."""
        r1 = adapter.is_round_over(_make_info(p1_round_wins=1))
        assert r1 == "P1"

        # Transition frames — no change
        assert adapter.is_round_over(_make_info(p1_round_wins=1)) is False

        # Round 2: P2 wins
        r2 = adapter.is_round_over(_make_info(p1_round_wins=1, p2_round_wins=1))
        assert r2 == "P2"

    def test_health_zero_without_win_counter_not_detected(self, adapter):
        """Health at 0 but round_wins unchanged → NOT a round end.
        This correctly ignores the 600-frame transition window."""
        result = adapter.is_round_over(_make_info(p2_health=-1, p1_round_wins=0))
        assert result is False


class TestIsMatchOver:
    def test_best_of_3_p1_wins(self, adapter):
        history = [{"winner": "P1"}, {"winner": "P2"}, {"winner": "P1"}]
        assert adapter.is_match_over(_make_info(), history, match_format=3) == "P1"

    def test_best_of_3_not_over(self, adapter):
        history = [{"winner": "P1"}, {"winner": "P2"}]
        assert adapter.is_match_over(_make_info(), history, match_format=3) is False

    def test_best_of_5_p2_wins(self, adapter):
        history = [{"winner": "P2"}] * 3
        assert adapter.is_match_over(_make_info(), history, match_format=5) == "P2"

    def test_best_of_1(self, adapter):
        history = [{"winner": "P1"}]
        assert adapter.is_match_over(_make_info(), history, match_format=1) == "P1"

    def test_empty_history(self, adapter):
        assert adapter.is_match_over(_make_info(), [], match_format=3) is False
