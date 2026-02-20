"""Verify FIX 3: P2 frame flip + action remap.

1. P2 observation is horizontally flipped vs P1
2. mirror_action swaps left/right directional bits
3. All adapters have DIRECTIONAL_INDICES set
"""
from __future__ import annotations

import cv2
import numpy as np

from rawl.game_adapters.base import GameAdapter
from rawl.game_adapters.kof98 import KOF98Adapter
from rawl.game_adapters.sf2ce import SF2CEAdapter
from rawl.game_adapters.sfiii3n import SFIII3NAdapter
from rawl.game_adapters.tektagt import TekkenTagAdapter


class TestP2FrameFlip:
    def test_p2_is_horizontally_flipped(self):
        """RetroEngine._translate_obs flips P2. Simulate the same logic."""
        # Create an asymmetric test frame (left side bright, right side dark)
        frame = np.zeros((200, 256, 3), dtype=np.uint8)
        frame[:, :128, :] = 255  # left half white

        obs_size = 256
        resized = cv2.resize(frame, (obs_size, obs_size))
        p2_frame = cv2.flip(resized, 1)  # horizontal flip

        # P1 sees left-white, P2 sees right-white (flipped)
        p1_left_mean = resized[:, :128, :].mean()
        p1_right_mean = resized[:, 128:, :].mean()
        p2_left_mean = p2_frame[:, :128, :].mean()
        p2_right_mean = p2_frame[:, 128:, :].mean()

        assert p1_left_mean > p1_right_mean, "P1 left half should be bright"
        assert p2_right_mean > p2_left_mean, "P2 right half should be bright (flipped)"
        assert abs(p1_left_mean - p2_right_mean) < 1.0, "Flip should swap halves"

    def test_flip_creates_new_array(self):
        """cv2.flip must not share memory with original."""
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        flipped = cv2.flip(frame, 1)

        # Modify original — flipped should not change
        original_flipped_copy = flipped.copy()
        frame[0, 0, 0] = 0
        assert np.array_equal(flipped, original_flipped_copy)


class TestMirrorAction:
    def test_sf2ce_mirror_swaps_left_right(self):
        """SF2CE: left=6, right=7. Mirror should swap these bits."""
        adapter = SF2CEAdapter()
        # Action: left=1, right=0 (pressing left only)
        action = np.zeros(12, dtype=np.int8)
        action[6] = 1  # left pressed
        action[7] = 0  # right not pressed

        mirrored = adapter.mirror_action(action)

        assert mirrored[6] == 0, "Left should now be 0 (was right's value)"
        assert mirrored[7] == 1, "Right should now be 1 (was left's value)"
        # Other buttons unchanged
        assert np.array_equal(mirrored[:6], action[:6])
        assert np.array_equal(mirrored[8:], action[8:])

    def test_mirror_preserves_other_buttons(self):
        """All buttons except left/right should be unchanged."""
        adapter = SF2CEAdapter()
        action = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=np.int8)
        mirrored = adapter.mirror_action(action)

        # Only indices 6 and 7 should swap
        for i in range(12):
            if i == 6:
                assert mirrored[i] == action[7]
            elif i == 7:
                assert mirrored[i] == action[6]
            else:
                assert mirrored[i] == action[i], f"Button {i} should be unchanged"

    def test_mirror_is_own_inverse(self):
        """Mirroring twice should return original action."""
        adapter = SF2CEAdapter()
        action = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1], dtype=np.int8)
        double_mirrored = adapter.mirror_action(adapter.mirror_action(action))
        assert np.array_equal(double_mirrored, action)

    def test_mirror_does_not_mutate_input(self):
        """mirror_action must return a copy, not modify in-place."""
        adapter = SF2CEAdapter()
        action = np.array([0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0], dtype=np.int8)
        original = action.copy()
        adapter.mirror_action(action)
        assert np.array_equal(action, original), "Input array was mutated"

    def test_base_adapter_no_indices_returns_same(self):
        """Adapter with empty DIRECTIONAL_INDICES returns action unchanged."""
        # Create a minimal concrete adapter
        class NoIndicesAdapter(GameAdapter):
            game_id = "test"
            adapter_version = "1.0.0"
            required_fields = []
            DIRECTIONAL_INDICES = {}

            def extract_state(self, info):
                pass

            def is_round_over(self, info, *, state=None):
                return False

            def is_match_over(self, info, round_history, *, state=None, match_format=3):
                return False

        adapter = NoIndicesAdapter()
        action = np.array([1, 0, 1], dtype=np.int8)
        result = adapter.mirror_action(action)
        assert result is action  # same object, not copied


class TestAllAdaptersHaveDirectionalIndices:
    def test_sf2ce(self):
        a = SF2CEAdapter()
        assert a.DIRECTIONAL_INDICES == {"left": 6, "right": 7}

    def test_sfiii3n(self):
        a = SFIII3NAdapter()
        assert a.DIRECTIONAL_INDICES == {"left": 6, "right": 7}

    def test_kof98(self):
        a = KOF98Adapter()
        assert a.DIRECTIONAL_INDICES == {"left": 6, "right": 7}

    def test_tektagt(self):
        a = TekkenTagAdapter()
        assert a.DIRECTIONAL_INDICES == {"left": 6, "right": 7}
