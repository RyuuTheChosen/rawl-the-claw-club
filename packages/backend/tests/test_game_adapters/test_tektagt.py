import pytest

from rawl.game_adapters.tektagt import TekkenTagAdapter


@pytest.fixture
def adapter():
    return TekkenTagAdapter()


def _make_info(
    p1_health=170, p1_tag=170,
    p2_health=170, p2_tag=170,
    p1_active=0, p2_active=0,
    timer=99,
):
    return {
        "P1": {
            "health": p1_health,
            "tag_health": p1_tag,
            "active_character": p1_active,
            "stage_side": 0,
        },
        "P2": {
            "health": p2_health,
            "tag_health": p2_tag,
            "active_character": p2_active,
            "stage_side": 1,
        },
        "round": 1,
        "timer": timer,
    }


class TestExtractState:
    def test_full_health(self, adapter):
        state = adapter.extract_state(_make_info())
        assert len(state.p1_team_health) == 2
        assert state.p1_team_health[0] == pytest.approx(1.0)
        assert state.p1_team_health[1] == pytest.approx(1.0)
        assert state.p1_eliminations == 0

    def test_tag_partner_ko(self, adapter):
        state = adapter.extract_state(_make_info(p1_tag=0))
        assert state.p1_team_health[1] == pytest.approx(0.0)
        assert state.p1_eliminations == 1

    def test_active_char_swap(self, adapter):
        state = adapter.extract_state(_make_info(p1_active=1, p1_health=85, p1_tag=170))
        assert state.p1_active_character == 1
        # When active=1, team[0]=tag(170/170), team[1]=active(85/170)
        assert state.p1_team_health[0] == pytest.approx(1.0)
        assert state.p1_team_health[1] == pytest.approx(0.5)


class TestIsRoundOver:
    def test_p1_point_ko(self, adapter):
        """Round ends if any P1 character is KO'd."""
        result = adapter.is_round_over(_make_info(p1_health=0))
        assert result == "P2"

    def test_p1_tag_ko(self, adapter):
        result = adapter.is_round_over(_make_info(p1_tag=0))
        assert result == "P2"

    def test_p2_ko(self, adapter):
        result = adapter.is_round_over(_make_info(p2_health=0))
        assert result == "P1"

    def test_double_ko(self, adapter):
        result = adapter.is_round_over(_make_info(p1_health=0, p2_health=0))
        assert result == "DRAW"

    def test_timeout_total_health(self, adapter):
        """Timeout uses total team health."""
        result = adapter.is_round_over(_make_info(p1_health=100, p1_tag=100, p2_health=50, p2_tag=50, timer=0))
        assert result == "P1"

    def test_timeout_draw(self, adapter):
        result = adapter.is_round_over(_make_info(p1_health=100, p1_tag=70, p2_health=70, p2_tag=100, timer=0))
        assert result == "DRAW"

    def test_not_over(self, adapter):
        assert adapter.is_round_over(_make_info()) is False


class TestIsMatchOver:
    def test_best_of_3_p1_wins(self, adapter):
        history = [{"winner": "P1"}, {"winner": "P1"}]
        assert adapter.is_match_over(_make_info(), history, match_format=3) == "P1"

    def test_best_of_3_not_over(self, adapter):
        history = [{"winner": "P1"}]
        assert adapter.is_match_over(_make_info(), history, match_format=3) is False

    def test_best_of_5(self, adapter):
        history = [{"winner": "P2"}] * 3
        assert adapter.is_match_over(_make_info(), history, match_format=5) == "P2"
