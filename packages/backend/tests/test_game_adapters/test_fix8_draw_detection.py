"""Verify FIX 8: SF2CE draw detection.

Simultaneous KO (both round_wins increment on same frame) must return "DRAW",
not always credit P1.
"""
from __future__ import annotations

from rawl.game_adapters.sf2ce import SF2CEAdapter


class TestSF2CEDrawDetection:
    def test_simultaneous_ko_returns_draw(self):
        """Both players' round_wins increment → DRAW."""
        adapter = SF2CEAdapter()
        # Initial state: both at 0 wins
        assert adapter._prev_p1_wins == 0
        assert adapter._prev_p2_wins == 0

        # Both win counters increment simultaneously
        info = {
            "P1": {"health": 0, "round_wins": 1},
            "P2": {"health": 0, "round_wins": 1},
        }
        result = adapter.is_round_over(info)
        assert result == "DRAW", f"Expected DRAW, got {result}"

    def test_p1_only_win(self):
        """Only P1 round_wins increments → P1."""
        adapter = SF2CEAdapter()
        info = {
            "P1": {"health": 100, "round_wins": 1},
            "P2": {"health": 0, "round_wins": 0},
        }
        result = adapter.is_round_over(info)
        assert result == "P1"

    def test_p2_only_win(self):
        """Only P2 round_wins increments → P2."""
        adapter = SF2CEAdapter()
        info = {
            "P1": {"health": 0, "round_wins": 0},
            "P2": {"health": 100, "round_wins": 1},
        }
        result = adapter.is_round_over(info)
        assert result == "P2"

    def test_no_change_returns_false(self):
        """No round_wins change → False."""
        adapter = SF2CEAdapter()
        info = {
            "P1": {"health": 100, "round_wins": 0},
            "P2": {"health": 100, "round_wins": 0},
        }
        result = adapter.is_round_over(info)
        assert result is False

    def test_sequential_rounds_track_correctly(self):
        """Multiple rounds: wins tracked via delta, not absolute value."""
        adapter = SF2CEAdapter()

        # Round 1: P1 wins
        info1 = {
            "P1": {"round_wins": 1},
            "P2": {"round_wins": 0},
        }
        assert adapter.is_round_over(info1) == "P1"

        # No change on next frame
        assert adapter.is_round_over(info1) is False

        # Round 2: P2 wins
        info2 = {
            "P1": {"round_wins": 1},
            "P2": {"round_wins": 1},
        }
        assert adapter.is_round_over(info2) == "P2"

        # Round 3: simultaneous
        info3 = {
            "P1": {"round_wins": 2},
            "P2": {"round_wins": 2},
        }
        assert adapter.is_round_over(info3) == "DRAW"

    def test_prev_wins_updated_on_draw(self):
        """After a DRAW, both _prev counters are updated."""
        adapter = SF2CEAdapter()
        info = {
            "P1": {"round_wins": 1},
            "P2": {"round_wins": 1},
        }
        adapter.is_round_over(info)
        assert adapter._prev_p1_wins == 1
        assert adapter._prev_p2_wins == 1
