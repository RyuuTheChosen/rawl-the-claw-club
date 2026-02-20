"""Verify FIX 10: Hide timer for SF2CE.

1. SF2CE adapter has has_round_timer=False
2. Other adapters have has_round_timer=True (default)
3. _translate_data_entry includes has_round_timer field
4. _build_data_message includes has_round_timer field
5. Backward compat: missing has_round_timer defaults to True
"""
from __future__ import annotations

from rawl.game_adapters.kof98 import KOF98Adapter
from rawl.game_adapters.sf2ce import SF2CEAdapter
from rawl.game_adapters.sfiii3n import SFIII3NAdapter
from rawl.game_adapters.tektagt import TekkenTagAdapter


class TestHasRoundTimerFlag:
    def test_sf2ce_no_timer(self):
        assert SF2CEAdapter().has_round_timer is False

    def test_sfiii3n_has_timer(self):
        assert SFIII3NAdapter().has_round_timer is True

    def test_kof98_has_timer(self):
        assert KOF98Adapter().has_round_timer is True

    def test_tektagt_has_timer(self):
        assert TekkenTagAdapter().has_round_timer is True


class TestReplayStreamerTranslation:
    def test_translate_data_entry_includes_timer_flag(self):
        from rawl.ws.replay_streamer import _translate_data_entry

        # SF2CE replay entry with has_round_timer=False
        entry = {
            "t": 1.5,
            "frame": 90,
            "p1_health": 0.8,
            "p2_health": 0.5,
            "round_number": 1,
            "timer": 0,
            "has_round_timer": False,
        }
        msg = _translate_data_entry("match-123", entry)
        assert msg["has_round_timer"] is False

    def test_translate_data_entry_defaults_true(self):
        """Old replays without has_round_timer default to True."""
        from rawl.ws.replay_streamer import _translate_data_entry

        entry = {
            "t": 1.5,
            "frame": 90,
            "p1_health": 0.8,
            "p2_health": 0.5,
            "round_number": 1,
            "timer": 45,
            # No has_round_timer key — backward compat
        }
        msg = _translate_data_entry("match-old", entry)
        assert msg["has_round_timer"] is True

    def test_translate_data_entry_explicit_true(self):
        from rawl.ws.replay_streamer import _translate_data_entry

        entry = {"has_round_timer": True}
        msg = _translate_data_entry("match-456", entry)
        assert msg["has_round_timer"] is True


class TestBroadcasterTranslation:
    def test_build_data_message_includes_timer_flag(self):
        from rawl.ws.broadcaster import _build_data_message

        # Simulated Redis stream data with has_round_timer
        raw_data = {
            b"p1_health": b"0.8",
            b"p2_health": b"0.5",
            b"round_number": b"1",
            b"timer": b"0",
            b"has_round_timer": b"0",  # False as int
        }
        msg = _build_data_message("match-123", raw_data)
        assert msg["has_round_timer"] is False

    def test_build_data_message_timer_true(self):
        from rawl.ws.broadcaster import _build_data_message

        raw_data = {
            b"has_round_timer": b"1",
        }
        msg = _build_data_message("match-456", raw_data)
        assert msg["has_round_timer"] is True

    def test_build_data_message_missing_defaults_true(self):
        """When has_round_timer is absent, default to True (1)."""
        from rawl.ws.broadcaster import _build_data_message

        raw_data = {}  # No has_round_timer key
        msg = _build_data_message("match-old", raw_data)
        assert msg["has_round_timer"] is True
