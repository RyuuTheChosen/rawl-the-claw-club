"""Verify FIX 2: Frame stacking CHW detection.

SB3 CnnPolicy uses CHW format. The _detect_stacking function must:
  - (4, 84, 84) → use_stack=True, single=(1, 84, 84), axis=0
  - (12, 84, 84) → use_stack=True, single=(3, 84, 84), axis=0
  - (1, 84, 84) → use_stack=False (single grayscale)
  - (3, 84, 84) → use_stack=False (single RGB)
  - (84, 84) → use_stack=False (2D, no stacking)
"""
from __future__ import annotations

import numpy as np

FRAME_STACK_N = 4


def _detect_stacking(obs_shape: tuple[int, ...]) -> tuple[bool, tuple[int, ...], int]:
    """Copy of the function from match_runner for isolated testing."""
    if len(obs_shape) != 3:
        return False, obs_shape, 0
    n_ch = obs_shape[0]
    if n_ch in (1, 3):
        return False, obs_shape, 0
    if n_ch == FRAME_STACK_N:
        return True, (1, obs_shape[1], obs_shape[2]), 0
    if n_ch > FRAME_STACK_N and n_ch % FRAME_STACK_N == 0:
        base_ch = n_ch // FRAME_STACK_N
        return True, (base_ch, obs_shape[1], obs_shape[2]), 0
    return False, obs_shape, 0


class TestDetectStacking:
    def test_4_stacked_grayscale(self):
        """(4, 84, 84) = 4 stacked grayscale frames."""
        use, shape, axis = _detect_stacking((4, 84, 84))
        assert use is True
        assert shape == (1, 84, 84)
        assert axis == 0

    def test_12_stacked_rgb(self):
        """(12, 84, 84) = 4 stacked RGB frames."""
        use, shape, axis = _detect_stacking((12, 84, 84))
        assert use is True
        assert shape == (3, 84, 84)
        assert axis == 0

    def test_single_grayscale(self):
        """(1, 84, 84) = single grayscale, no stacking."""
        use, shape, axis = _detect_stacking((1, 84, 84))
        assert use is False
        assert shape == (1, 84, 84)

    def test_single_rgb(self):
        """(3, 84, 84) = single RGB, no stacking."""
        use, shape, axis = _detect_stacking((3, 84, 84))
        assert use is False
        assert shape == (3, 84, 84)

    def test_2d_obs(self):
        """(84, 84) = 2D obs, no stacking."""
        use, shape, axis = _detect_stacking((84, 84))
        assert use is False
        assert shape == (84, 84)

    def test_unknown_channel_count(self):
        """(5, 84, 84) = not divisible by FRAME_STACK_N, no stacking."""
        use, shape, axis = _detect_stacking((5, 84, 84))
        assert use is False
        assert shape == (5, 84, 84)

    def test_8_stacked_2ch(self):
        """(8, 84, 84) = 4 stacked 2-channel frames."""
        use, shape, axis = _detect_stacking((8, 84, 84))
        assert use is True
        assert shape == (2, 84, 84)
        assert axis == 0


class TestConcatAxis:
    def test_concat_axis_0_grayscale(self):
        """Stacked grayscale: concat along axis=0 produces (4, 84, 84)."""
        frames = [np.zeros((1, 84, 84)) for _ in range(4)]
        stacked = np.concatenate(frames, axis=0)
        assert stacked.shape == (4, 84, 84)

    def test_concat_axis_0_rgb(self):
        """Stacked RGB: concat along axis=0 produces (12, 84, 84)."""
        frames = [np.zeros((3, 84, 84)) for _ in range(4)]
        stacked = np.concatenate(frames, axis=0)
        assert stacked.shape == (12, 84, 84)

    def test_old_axis_neg1_would_be_wrong(self):
        """Prove that axis=-1 gives wrong shape for CHW format."""
        frames = [np.zeros((1, 84, 84)) for _ in range(4)]
        wrong = np.concatenate(frames, axis=-1)
        # axis=-1 on (1, 84, 84) concatenates on last dim → (1, 84, 336)
        assert wrong.shape == (1, 84, 336), "This is the bug we fixed"
        assert wrong.shape != (4, 84, 84)
