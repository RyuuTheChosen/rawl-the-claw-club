import pytest

from rawl.game_adapters.sfiii3n import SFIII3NAdapter
from rawl.game_adapters.errors import AdapterValidationError


@pytest.fixture
def adapter():
    return SFIII3NAdapter()


def _make_info(p1_health=176, p2_health=176, timer=99, round_num=1, stage_side=0):
    return {
        "P1": {"health": p1_health, "round": round_num, "timer": timer, "stage_side": stage_side},
        "P2": {"health": p2_health, "round": round_num, "timer": timer, "stage_side": 1},
        "round": round_num,
        "timer": timer,
    }


class TestValidation:
    def test_valid_info(self, adapter):
        info = _make_info()
        adapter.validate_info(info)  # Should not raise

    def test_missing_health(self, adapter):
        info = {"P1": {"round": 1, "timer": 99, "stage_side": 0}, "P2": {"round": 1, "timer": 99, "stage_side": 0}}
        with pytest.raises(AdapterValidationError) as exc_info:
            adapter.validate_info(info)
        assert "health" in str(exc_info.value)

    def test_missing_player(self, adapter):
        info = {"P1": {"health": 176, "round": 1, "timer": 99, "stage_side": 0}}
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


class TestIsRoundOver:
    def test_p1_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=0)) == "P2"

    def test_p2_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p2_health=0)) == "P1"

    def test_double_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=0, p2_health=0)) == "DRAW"

    def test_timeout_p1_wins(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=100, p2_health=50, timer=0)) == "P1"

    def test_timeout_p2_wins(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=30, p2_health=80, timer=0)) == "P2"

    def test_timeout_draw(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=100, p2_health=100, timer=0)) == "DRAW"

    def test_not_over(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=100, p2_health=100, timer=50)) is False


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
