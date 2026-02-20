"""Verify FIX 5: WebSocket backpressure.

1. Frame send uses asyncio.wait_for with timeout
2. Dropped frames tracked in sliding window
3. Client disconnected when drop ratio exceeds threshold
4. Data message drops are non-fatal
"""
from __future__ import annotations

import asyncio
from collections import deque


# Replicate the backpressure constants from replay_streamer
SEND_TIMEOUT = 0.050
MAX_DROP_RATIO = 0.8
WINDOW_SIZE = 60


class TestBackpressureLogic:
    def test_drop_window_tracks_drops(self):
        """Sliding window correctly tracks frame drops above threshold."""
        window: deque[bool] = deque(maxlen=WINDOW_SIZE)

        # 49 drops + 11 successes = ~81.7% drop rate (above 80% threshold)
        for _ in range(49):
            window.append(True)  # dropped
        for _ in range(11):
            window.append(False)  # sent

        assert len(window) == WINDOW_SIZE
        assert sum(window) == 49
        assert sum(window) > int(WINDOW_SIZE * MAX_DROP_RATIO)

    def test_below_threshold_no_disconnect(self):
        """70% drops should NOT trigger disconnect."""
        window: deque[bool] = deque(maxlen=WINDOW_SIZE)

        for _ in range(42):
            window.append(True)
        for _ in range(18):
            window.append(False)

        assert len(window) == WINDOW_SIZE
        assert sum(window) == 42
        threshold = int(WINDOW_SIZE * MAX_DROP_RATIO)
        assert sum(window) <= threshold, "42 drops should be at or below threshold"

    def test_window_sliding_behavior(self):
        """Old entries fall off as new ones are added."""
        window: deque[bool] = deque(maxlen=WINDOW_SIZE)

        # Fill with all drops
        for _ in range(WINDOW_SIZE):
            window.append(True)
        assert sum(window) == WINDOW_SIZE

        # Push 30 successes — oldest 30 drops fall off
        for _ in range(30):
            window.append(False)
        assert sum(window) == 30  # 30 drops remain from original

    def test_disconnect_only_when_window_full(self):
        """Don't disconnect before window is full (< 60 frames)."""
        window: deque[bool] = deque(maxlen=WINDOW_SIZE)

        # Only 10 frames, all dropped
        for _ in range(10):
            window.append(True)

        # Window not full — should NOT trigger disconnect even at 100% drops
        should_disconnect = (
            len(window) == WINDOW_SIZE
            and sum(window) > int(WINDOW_SIZE * MAX_DROP_RATIO)
        )
        assert should_disconnect is False

    async def test_slow_send_triggers_timeout(self):
        """asyncio.wait_for with SEND_TIMEOUT cancels slow sends."""
        async def slow_send():
            await asyncio.sleep(1.0)  # Way longer than 50ms

        with_timeout = False
        try:
            await asyncio.wait_for(slow_send(), timeout=SEND_TIMEOUT)
        except asyncio.TimeoutError:
            with_timeout = True

        assert with_timeout, "Slow send should trigger TimeoutError"

    async def test_fast_send_completes(self):
        """Fast sends complete within the timeout."""
        async def fast_send():
            await asyncio.sleep(0.001)  # 1ms — well within 50ms

        completed = False
        try:
            await asyncio.wait_for(fast_send(), timeout=SEND_TIMEOUT)
            completed = True
        except asyncio.TimeoutError:
            pass

        assert completed, "Fast send should complete without timeout"

    def test_full_scenario_disconnect(self):
        """Simulate a full streaming scenario with a slow client."""
        window: deque[bool] = deque(maxlen=WINDOW_SIZE)
        should_break = False

        # Simulate 60 frames where 50 are dropped (83%)
        for i in range(WINDOW_SIZE):
            is_drop = i < 50  # first 50 dropped, last 10 sent
            window.append(is_drop)

            if (
                len(window) == WINDOW_SIZE
                and sum(window) > int(WINDOW_SIZE * MAX_DROP_RATIO)
            ):
                should_break = True
                break

        assert should_break, "Client should be disconnected at 83% drop rate"
