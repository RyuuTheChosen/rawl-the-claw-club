import pytest

from rawl.game_adapters.kof98 import KOF98Adapter
from rawl.game_adapters.errors import AdapterValidationError


@pytest.fixture
def adapter():
    return KOF98Adapter()


def _make_info(
    p1_health=103, p2_health=103,
    p1_chars=None, p2_chars=None,
    p1_active=0, p2_active=0,
    timer=99,
):
    p1_chars = p1_chars or [103, 103, 103]
    p2_chars = p2_chars or [103, 103, 103]
    return {
        "P1": {
            "health": p1_health,
            "active_character": p1_active,
            "char_0_health": p1_chars[0],
            "char_1_health": p1_chars[1],
            "char_2_health": p1_chars[2],
            "stage_side": 0,
        },
        "P2": {
            "health": p2_health,
            "active_character": p2_active,
            "char_0_health": p2_chars[0],
            "char_1_health": p2_chars[1],
            "char_2_health": p2_chars[2],
            "stage_side": 1,
        },
        "round": 1,
        "timer": timer,
    }


class TestValidation:
    def test_valid_info(self, adapter):
        adapter.validate_info(_make_info())  # Should not raise

    def test_missing_char_health(self, adapter):
        info = _make_info()
        del info["P1"]["char_2_health"]
        with pytest.raises(AdapterValidationError):
            adapter.validate_info(info)


class TestExtractState:
    def test_full_health_team(self, adapter):
        state = adapter.extract_state(_make_info())
        assert len(state.p1_team_health) == 3
        assert len(state.p2_team_health) == 3
        assert all(h == pytest.approx(1.0) for h in state.p1_team_health)

    def test_partial_elimination(self, adapter):
        state = adapter.extract_state(_make_info(p1_chars=[103, 0, 103]))
        assert state.p1_team_health[1] == pytest.approx(0.0)
        assert state.p1_eliminations == 1

    def test_active_character_tracking(self, adapter):
        state = adapter.extract_state(_make_info(p1_active=2))
        assert state.p1_active_character == 2

    def test_full_team_eliminated(self, adapter):
        state = adapter.extract_state(_make_info(p2_chars=[0, 0, 0], p2_health=0))
        assert state.p2_eliminations == 3


class TestIsRoundOver:
    def test_p1_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=0)) == "P2"

    def test_p2_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p2_health=0)) == "P1"

    def test_double_ko(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=0, p2_health=0)) == "DRAW"

    def test_timeout(self, adapter):
        assert adapter.is_round_over(_make_info(p1_health=80, p2_health=40, timer=0)) == "P1"

    def test_not_over(self, adapter):
        assert adapter.is_round_over(_make_info()) is False


class TestIsMatchOver:
    def test_team_eliminated_p2_wins(self, adapter):
        info = _make_info(p1_chars=[0, 0, 0], p1_health=0)
        result = adapter.is_match_over(info, [], match_format=3)
        assert result == "P2"

    def test_team_eliminated_p1_wins(self, adapter):
        info = _make_info(p2_chars=[0, 0, 0], p2_health=0)
        result = adapter.is_match_over(info, [], match_format=3)
        assert result == "P1"

    def test_not_over_one_alive(self, adapter):
        info = _make_info(p1_chars=[0, 0, 50], p1_active=2, p1_health=50)
        result = adapter.is_match_over(info, [], match_format=3)
        assert result is False

    def test_ignores_match_format(self, adapter):
        """KOF98 uses team elimination, not best-of-N."""
        info = _make_info(p2_chars=[0, 0, 0], p2_health=0)
        assert adapter.is_match_over(info, [], match_format=1) == "P1"
        assert adapter.is_match_over(info, [], match_format=5) == "P1"
