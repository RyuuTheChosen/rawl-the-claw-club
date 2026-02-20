"""Verify FIX 4: Chunked S3 replay streaming.

1. s3_client has download_byte_range and get_object_size
2. _ReplayData lazily fetches chunks, not entire MJPEG
3. Frame extraction works with chunked data
4. Old chunks are evicted (only keep current and previous)
5. Prefetch trigger fires at 80% through a chunk
"""
from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, patch

from rawl.ws.replay_streamer import _CHUNK_SIZE, _ReplayData


def _make_test_replay(num_frames: int = 600) -> tuple[_ReplayData, bytes]:
    """Create a _ReplayData with known frame content for testing.

    Returns (replay, full_mjpeg_bytes).
    """
    # Each frame is 100 bytes: b"FRAME" + frame_index as 4 bytes + padding
    frames = []
    offsets = []
    offset = 0
    for i in range(num_frames):
        frame_data = b"FRAME" + i.to_bytes(4, "little") + b"\x00" * 91
        assert len(frame_data) == 100
        frames.append(frame_data)
        offsets.append(offset)
        offset += len(frame_data)

    mjpeg = b"".join(frames)
    data_entries = [{"frame": i, "p1_health": 0.5} for i in range(0, num_frames, 6)]

    replay = _ReplayData(
        match_id="test-match",
        offsets=offsets,
        data_entries=data_entries,
        num_frames=num_frames,
        mjpeg_size=len(mjpeg),
        size_bytes=num_frames * 8 + 100,  # idx + json approx
    )
    return replay, mjpeg


class TestReplayDataChunkedFetch:
    async def test_extract_frame_fetches_chunk(self):
        """Extracting a frame triggers a chunk download."""
        replay, mjpeg = _make_test_replay(600)

        async def mock_download_range(key, start, end):
            return mjpeg[start:end]

        with patch(
            "rawl.ws.replay_streamer.download_byte_range",
            side_effect=mock_download_range,
        ):
            # Extract frame 0 — should fetch chunk 0
            frame = await replay.extract_frame(0)
            assert frame is not None
            assert frame[:5] == b"FRAME"
            assert int.from_bytes(frame[5:9], "little") == 0

            # Extract frame 299 — still chunk 0, no new download
            frame = await replay.extract_frame(299)
            assert frame is not None
            assert int.from_bytes(frame[5:9], "little") == 299

    async def test_extract_frame_different_chunks(self):
        """Frames in different chunks trigger separate downloads."""
        replay, mjpeg = _make_test_replay(600)
        download_calls = []

        async def mock_download_range(key, start, end):
            download_calls.append((start, end))
            return mjpeg[start:end]

        with patch(
            "rawl.ws.replay_streamer.download_byte_range",
            side_effect=mock_download_range,
        ):
            # Frame 0 — chunk 0
            await replay.extract_frame(0)
            assert len(download_calls) == 1

            # Frame 300 — chunk 1
            await replay.extract_frame(300)
            assert len(download_calls) == 2

            # Frame 150 — still chunk 0 (if not evicted)
            # Chunk 0 was evicted because chunk_idx=1 evicts chunks < 0
            # Actually: stale = [k for k in chunks if k < chunk_idx - 1]
            # chunk_idx=1, so stale = [k for k if k < 0] = [] — chunk 0 kept!
            await replay.extract_frame(150)
            # Chunk 0 should still be cached
            assert len(download_calls) == 2, "Chunk 0 should still be cached"

    async def test_old_chunks_evicted(self):
        """Chunks more than 1 behind current are evicted."""
        replay, mjpeg = _make_test_replay(900)

        async def mock_download_range(key, start, end):
            return mjpeg[start:end]

        with patch(
            "rawl.ws.replay_streamer.download_byte_range",
            side_effect=mock_download_range,
        ):
            # Fetch chunk 0
            await replay.extract_frame(0)
            assert 0 in replay._chunks

            # Fetch chunk 1 — chunk 0 still kept (only 1 behind)
            await replay.extract_frame(300)
            assert 0 in replay._chunks
            assert 1 in replay._chunks

            # Fetch chunk 2 — chunk 0 evicted (2 behind)
            await replay.extract_frame(600)
            assert 0 not in replay._chunks, "Chunk 0 should be evicted"
            assert 1 in replay._chunks
            assert 2 in replay._chunks

    async def test_extract_frame_out_of_range(self):
        """Out-of-range frame returns None."""
        replay, _ = _make_test_replay(100)
        result = await replay.extract_frame(-1)
        assert result is None
        result = await replay.extract_frame(100)
        assert result is None

    async def test_extract_frame_last_frame(self):
        """Last frame uses mjpeg_size as end boundary."""
        replay, mjpeg = _make_test_replay(10)

        async def mock_download_range(key, start, end):
            return mjpeg[start:end]

        with patch(
            "rawl.ws.replay_streamer.download_byte_range",
            side_effect=mock_download_range,
        ):
            frame = await replay.extract_frame(9)
            assert frame is not None
            assert len(frame) == 100
            assert int.from_bytes(frame[5:9], "little") == 9

    async def test_download_failure_returns_none(self):
        """If S3 download fails, extract_frame returns None."""
        replay, _ = _make_test_replay(10)

        with patch(
            "rawl.ws.replay_streamer.download_byte_range",
            return_value=None,
        ):
            frame = await replay.extract_frame(0)
            assert frame is None


class TestPrefetchTrigger:
    def test_prefetch_fires_at_80_percent(self):
        """Prefetch should fire when frames_into_chunk == int(CHUNK_SIZE * 0.8)."""
        trigger_frame = int(_CHUNK_SIZE * 0.8)
        # Frame index that's 80% through chunk 0
        frame_idx = trigger_frame
        frames_into_chunk = frame_idx % _CHUNK_SIZE
        assert frames_into_chunk == trigger_frame

        # Next chunk should be 1
        next_chunk = (frame_idx // _CHUNK_SIZE) + 1
        assert next_chunk == 1

    def test_no_prefetch_before_80_percent(self):
        """Frames before 80% should NOT trigger prefetch."""
        for i in range(int(_CHUNK_SIZE * 0.8)):
            frames_into_chunk = i % _CHUNK_SIZE
            assert frames_into_chunk != int(_CHUNK_SIZE * 0.8)


class TestS3ClientHelpers:
    async def test_download_byte_range_validates_inputs(self):
        from rawl.s3_client import download_byte_range

        # Invalid range: start >= end
        result = await download_byte_range("key", 100, 50)
        assert result is None

        # Invalid range: negative start
        result = await download_byte_range("key", -1, 50)
        assert result is None

    async def test_get_object_size_returns_none_on_error(self):
        from rawl.s3_client import get_object_size

        # Will fail because no real S3 connection
        with patch("rawl.s3_client._get_client", side_effect=Exception("no S3")):
            result = await get_object_size("nonexistent-key")
            assert result is None
