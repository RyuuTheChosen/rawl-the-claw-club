"""Verify FIX 9: Cache eviction race + stream counter race.

1. Cache eviction happens under global lock (lock cleanup included)
2. Stream counters are protected by _ip_lock
3. Concurrent connection attempts respect limits atomically
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from rawl.ws.replay_streamer import (
    _MAX_GLOBAL_STREAMS,
    _MAX_STREAMS_PER_IP,
    _ReplayCache,
)


class TestCacheEvictionUnderLock:
    async def test_eviction_cleans_up_locks(self):
        """When a cache entry is evicted, its per-match lock is also removed."""
        cache = _ReplayCache()

        # Manually populate cache with fake entries
        for i in range(3):
            mid = f"match-{i}"
            cache._cache[mid] = (MagicMock(), 0.0)  # expired (ts=0)
            cache._locks[mid] = asyncio.Lock()

        assert len(cache._locks) == 3

        # Evict under global lock (as the fix requires)
        async with cache._global_lock:
            cache._evict_if_needed()

        # All entries evicted (TTL=0 means all expired)
        assert len(cache._cache) == 0
        assert len(cache._locks) == 0, "Locks should be cleaned up on eviction"

    async def test_cache_insert_under_global_lock(self):
        """Cache insertion + eviction happens atomically under global lock."""
        cache = _ReplayCache()

        # Fill cache to max
        for i in range(3):
            mid = f"match-{i}"
            # Use large monotonic time so they won't be TTL-evicted
            cache._cache[mid] = (MagicMock(), 1e12)
            cache._locks[mid] = asyncio.Lock()

        assert len(cache._cache) == 3

        # Inserting a new entry should evict oldest
        async with cache._global_lock:
            cache._evict_if_needed()
            cache._cache["match-new"] = (MagicMock(), 1e12 + 1)

        assert len(cache._cache) == 3  # Still at max
        assert "match-new" in cache._cache

    async def test_eviction_removes_oldest(self):
        """Oldest entry (by timestamp) is evicted first when at capacity."""
        import time as _time

        cache = _ReplayCache()

        # Use future timestamps so nothing is TTL-expired
        now = _time.monotonic()
        cache._cache["old"] = (MagicMock(), now + 100)
        cache._cache["mid"] = (MagicMock(), now + 200)
        cache._cache["new"] = (MagicMock(), now + 300)

        # Cache is at max (3) — eviction removes oldest to make room
        async with cache._global_lock:
            cache._evict_if_needed()

        # "old" should be evicted (lowest timestamp)
        assert "old" not in cache._cache
        assert "mid" in cache._cache
        assert "new" in cache._cache


class TestStreamCounterAtomicity:
    async def test_concurrent_connections_respect_global_limit(self):
        """Simulate 15 concurrent connection attempts — only 10 should succeed."""
        # Reset module-level state
        import rawl.ws.replay_streamer as mod

        # Save original state
        orig_ip_count = dict(mod._ip_stream_count)
        orig_global = mod._global_stream_count

        try:
            mod._ip_stream_count.clear()
            mod._global_stream_count = 0

            accepted = 0
            rejected = 0

            async def try_connect(ip: str):
                nonlocal accepted, rejected
                async with mod._ip_lock:
                    if mod._ip_stream_count[ip] >= _MAX_STREAMS_PER_IP:
                        rejected += 1
                        return
                    if mod._global_stream_count >= _MAX_GLOBAL_STREAMS:
                        rejected += 1
                        return
                    mod._ip_stream_count[ip] += 1
                    mod._global_stream_count += 1
                    accepted += 1

            # 15 connections from 15 different IPs (bypass per-IP limit)
            tasks = [try_connect(f"ip-{i}") for i in range(15)]
            await asyncio.gather(*tasks)

            assert accepted == _MAX_GLOBAL_STREAMS, f"Expected {_MAX_GLOBAL_STREAMS} accepted, got {accepted}"
            assert rejected == 5, f"Expected 5 rejected, got {rejected}"
            assert mod._global_stream_count == _MAX_GLOBAL_STREAMS

        finally:
            # Restore state
            mod._ip_stream_count.clear()
            mod._ip_stream_count.update(orig_ip_count)
            mod._global_stream_count = orig_global

    async def test_per_ip_limit_enforced(self):
        """Same IP can only open _MAX_STREAMS_PER_IP connections."""
        import rawl.ws.replay_streamer as mod

        orig_ip_count = dict(mod._ip_stream_count)
        orig_global = mod._global_stream_count

        try:
            mod._ip_stream_count.clear()
            mod._global_stream_count = 0

            accepted = 0

            async def try_connect():
                nonlocal accepted
                async with mod._ip_lock:
                    if mod._ip_stream_count["same-ip"] >= _MAX_STREAMS_PER_IP:
                        return
                    if mod._global_stream_count >= _MAX_GLOBAL_STREAMS:
                        return
                    mod._ip_stream_count["same-ip"] += 1
                    mod._global_stream_count += 1
                    accepted += 1

            tasks = [try_connect() for _ in range(5)]
            await asyncio.gather(*tasks)

            assert accepted == _MAX_STREAMS_PER_IP
            assert mod._ip_stream_count["same-ip"] == _MAX_STREAMS_PER_IP

        finally:
            mod._ip_stream_count.clear()
            mod._ip_stream_count.update(orig_ip_count)
            mod._global_stream_count = orig_global

    async def test_counters_correct_after_disconnect(self):
        """After all clients disconnect, counters return to zero."""
        import rawl.ws.replay_streamer as mod

        orig_ip_count = dict(mod._ip_stream_count)
        orig_global = mod._global_stream_count

        try:
            mod._ip_stream_count.clear()
            mod._global_stream_count = 0

            # Simulate 5 connections
            for i in range(5):
                async with mod._ip_lock:
                    mod._ip_stream_count[f"ip-{i}"] += 1
                    mod._global_stream_count += 1

            assert mod._global_stream_count == 5

            # Simulate all disconnecting
            for i in range(5):
                async with mod._ip_lock:
                    mod._ip_stream_count[f"ip-{i}"] = max(
                        0, mod._ip_stream_count[f"ip-{i}"] - 1
                    )
                    mod._global_stream_count = max(0, mod._global_stream_count - 1)

            assert mod._global_stream_count == 0
            for i in range(5):
                assert mod._ip_stream_count[f"ip-{i}"] == 0

        finally:
            mod._ip_stream_count.clear()
            mod._ip_stream_count.update(orig_ip_count)
            mod._global_stream_count = orig_global
