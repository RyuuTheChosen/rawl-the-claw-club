"""WebSocket endpoint for streaming pre-computed match replays at 60fps.

Architecture:
  _ReplayData  — immutable container for parsed replay (MJPEG + index + data)
  _ReplayCache — module-level LRU with TTL and memory cap
  _translate_data_entry — converts raw state dict to 16-field frontend format
  replay_endpoint — WebSocket handler
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
import uuid as _uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rawl.s3_client import download_byte_range, download_bytes, get_object_size

logger = logging.getLogger(__name__)

replay_router = APIRouter()

# ─── Replay data container ───────────────────────────────────────────────────

_CHUNK_SIZE = 300  # frames per chunk (~5 seconds at 60fps)


@dataclass
class _ReplayData:
    """Replay container that lazily fetches MJPEG chunks from S3."""

    match_id: str
    offsets: list[int]
    data_entries: list[dict]
    num_frames: int
    mjpeg_size: int
    size_bytes: int  # metadata size for cache accounting

    def __post_init__(self) -> None:
        self._chunks: dict[int, bytes] = {}
        self._chunk_lock = asyncio.Lock()

    async def ensure_chunk(self, chunk_idx: int) -> bool:
        """Download chunk from S3 if not cached. Evicts old chunks."""
        if chunk_idx in self._chunks:
            return True
        async with self._chunk_lock:
            if chunk_idx in self._chunks:
                return True  # double-check after lock
            start_frame = chunk_idx * _CHUNK_SIZE
            end_frame = min(start_frame + _CHUNK_SIZE, self.num_frames)
            byte_start = self.offsets[start_frame]
            byte_end = (
                self.offsets[end_frame]
                if end_frame < self.num_frames
                else self.mjpeg_size
            )
            data = await download_byte_range(
                f"replays/{self.match_id}.mjpeg", byte_start, byte_end
            )
            if data is None:
                return False
            self._chunks[chunk_idx] = data
            # Evict chunks more than 1 behind current
            stale = [k for k in self._chunks if k < chunk_idx - 1]
            for k in stale:
                del self._chunks[k]
            return True

    async def extract_frame(self, index: int) -> bytes | None:
        """Extract single JPEG frame, fetching chunk on demand."""
        if index < 0 or index >= self.num_frames:
            return None
        chunk_idx = index // _CHUNK_SIZE
        if not await self.ensure_chunk(chunk_idx):
            return None
        # Compute local offset within chunk
        chunk_start_frame = chunk_idx * _CHUNK_SIZE
        chunk_byte_base = self.offsets[chunk_start_frame]
        local_start = self.offsets[index] - chunk_byte_base
        local_end = (
            (self.offsets[index + 1] - chunk_byte_base)
            if index + 1 < self.num_frames
            else len(self._chunks[chunk_idx])
        )
        return self._chunks[chunk_idx][local_start:local_end]


# ─── Replay cache ────────────────────────────────────────────────────────────

_MAX_CACHE_ENTRIES = 3
_CACHE_TTL_SECONDS = 600  # 10 minutes


class _ReplayCache:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[_ReplayData, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get(self, match_id: str) -> _ReplayData | None:
        """Get replay data, downloading from S3 if not cached."""
        # Get or create per-match lock under global lock
        async with self._global_lock:
            if match_id not in self._locks:
                self._locks[match_id] = asyncio.Lock()
            lock = self._locks[match_id]

        async with lock:
            # Check cache hit
            if match_id in self._cache:
                data, _ = self._cache[match_id]
                self._cache[match_id] = (data, time.monotonic())
                return data

            # Cache miss — download
            replay = await self._download(match_id)
            if replay is None:
                return None

            # Insert into cache under global lock
            async with self._global_lock:
                self._evict_if_needed()
                self._cache[match_id] = (replay, time.monotonic())
            return replay

    async def _download(self, match_id: str) -> _ReplayData | None:
        """Download only index + JSON sidecar (not MJPEG blob)."""
        idx_bytes = await download_bytes(f"replays/{match_id}.idx")
        json_bytes = await download_bytes(f"replays/{match_id}.json")
        if not idx_bytes or not json_bytes:
            logger.error(
                "Failed to download replay metadata",
                extra={"match_id": match_id},
            )
            return None

        mjpeg_size = await get_object_size(f"replays/{match_id}.mjpeg")
        if mjpeg_size is None or mjpeg_size == 0:
            logger.error(
                "Failed to get MJPEG size", extra={"match_id": match_id}
            )
            return None

        # Parse index (u64 LE offsets)
        num_frames = len(idx_bytes) // 8
        if num_frames == 0:
            logger.error("Empty index file", extra={"match_id": match_id})
            return None
        offsets = list(struct.unpack(f"<{num_frames}Q", idx_bytes))

        # Validate offsets are monotonically increasing and within bounds
        for i, offset in enumerate(offsets):
            if offset >= mjpeg_size:
                logger.error(
                    "Corrupt index: offset beyond MJPEG",
                    extra={"frame": i, "offset": offset},
                )
                return None
            if i > 0 and offset <= offsets[i - 1]:
                logger.error(
                    "Corrupt index: non-monotonic offset",
                    extra={"frame": i},
                )
                return None

        # Parse data sidecar
        try:
            data_entries = json.loads(json_bytes)
        except json.JSONDecodeError:
            logger.error("Corrupt JSON sidecar", extra={"match_id": match_id})
            return None

        return _ReplayData(
            match_id=match_id,
            offsets=offsets,
            data_entries=data_entries,
            num_frames=num_frames,
            mjpeg_size=mjpeg_size,
            size_bytes=len(idx_bytes) + len(json_bytes),
        )

    def _evict_if_needed(self) -> None:
        """Evict oldest entry if cache is full. Also evict expired entries.

        Must be called under self._global_lock.
        """
        now = time.monotonic()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > _CACHE_TTL_SECONDS]
        for k in expired:
            del self._cache[k]
            self._locks.pop(k, None)

        while len(self._cache) >= _MAX_CACHE_ENTRIES:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
            self._locks.pop(oldest, None)


_cache = _ReplayCache()


# ─── Data translation ────────────────────────────────────────────────────────

def _translate_data_entry(match_id: str, entry: dict) -> dict:
    """Translate raw state dict to 16-field frontend format.

    Same mapping as broadcaster._build_data_message but operating on
    native Python dicts (not Redis byte-encoded data).
    """
    return {
        "match_id": match_id,
        "timestamp": str(entry.get("t", "")),
        "health_a": float(entry.get("p1_health", 0) or 0),
        "health_b": float(entry.get("p2_health", 0) or 0),
        "round": int(entry.get("round_number", 0) or 0),
        "timer": int(entry.get("timer", 0) or 0),
        "status": "replay",
        "round_winner": entry.get("round_winner"),
        "match_winner": entry.get("match_winner"),
        "team_health_a": entry.get("p1_team_health"),
        "team_health_b": entry.get("p2_team_health"),
        "active_char_a": entry.get("p1_active_character"),
        "active_char_b": entry.get("p2_active_character"),
        "has_round_timer": entry.get("has_round_timer", True),
        "odds_a": 0,
        "odds_b": 0,
        "pool_total": 0,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _find_nearest_entry(
    entries: list[dict], frame: int, start_idx: int,
) -> tuple[dict, int] | None:
    """Find the data entry with the largest 'frame' value <= frame, starting from start_idx.

    Returns (entry, index) or None.
    """
    result = None
    result_idx = start_idx
    for i in range(start_idx, len(entries)):
        entry_frame = entries[i].get("frame", 0)
        if entry_frame <= frame:
            result = entries[i]
            result_idx = i
        else:
            break
    if result is None:
        return None
    return result, result_idx


def _get_client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = websocket.client
    return client.host if client else "unknown"


async def _watch_disconnect(websocket: WebSocket, event: asyncio.Event) -> None:
    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
    except Exception:
        pass
    event.set()


# ─── WebSocket endpoint ─────────────────────────────────────────────────────

_MAX_STREAMS_PER_IP = 2
_MAX_GLOBAL_STREAMS = 10
_ip_stream_count: dict[str, int] = defaultdict(int)
_global_stream_count = 0
_ip_lock = asyncio.Lock()

REPLAY_FPS = 60
DATA_INTERVAL = 6  # Send data every 6th frame (=10Hz at 60fps)


@replay_router.websocket("/replay/{match_id}")
async def replay_endpoint(websocket: WebSocket, match_id: str) -> None:
    global _global_stream_count  # mutated under _ip_lock

    # Validate match_id is a UUID
    try:
        _uuid.UUID(match_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid match_id")
        return

    # Connection limits — acquire slot under lock
    client_ip = _get_client_ip(websocket)
    async with _ip_lock:
        if _ip_stream_count[client_ip] >= _MAX_STREAMS_PER_IP:
            await websocket.close(code=4029, reason="Too many replay streams")
            return
        if _global_stream_count >= _MAX_GLOBAL_STREAMS:
            await websocket.close(code=4029, reason="Server at replay capacity")
            return
        _ip_stream_count[client_ip] += 1
        _global_stream_count += 1

    # Accept AFTER acquiring slot
    await websocket.accept()

    try:
        # Load replay (from cache or S3)
        replay = await _cache.get(match_id)
        if replay is None:
            await websocket.close(code=4004, reason="Replay not found")
            return

        if replay.num_frames == 0:
            await websocket.close(code=4004, reason="Empty replay")
            return

        # Set up disconnect detection
        disconnected = asyncio.Event()
        watcher = asyncio.create_task(_watch_disconnect(websocket, disconnected))

        # Stream frames at 60fps with drift correction and backpressure
        stream_start = time.monotonic()
        data_cursor = 0
        SEND_TIMEOUT = 0.050  # 50ms — ~3 frame periods at 60fps
        MAX_DROP_RATIO = 0.8  # disconnect if >80% drops in window
        drop_window: deque[bool] = deque(maxlen=60)

        try:
            for i in range(replay.num_frames):
                if disconnected.is_set():
                    break

                # Extract frame (fetches S3 chunk on demand)
                frame_bytes = await replay.extract_frame(i)
                if frame_bytes is None:
                    logger.error(
                        "Frame extraction failed",
                        extra={"match_id": match_id, "frame": i},
                    )
                    break

                # Prefetch next chunk when entering the last 20% of current
                frames_into_chunk = i % _CHUNK_SIZE
                if frames_into_chunk == int(_CHUNK_SIZE * 0.8):
                    next_chunk = (i // _CHUNK_SIZE) + 1
                    if next_chunk * _CHUNK_SIZE < replay.num_frames:
                        asyncio.create_task(replay.ensure_chunk(next_chunk))

                # Send frame with backpressure
                try:
                    await asyncio.wait_for(
                        websocket.send_bytes(frame_bytes), timeout=SEND_TIMEOUT
                    )
                    drop_window.append(False)
                except asyncio.TimeoutError:
                    drop_window.append(True)
                    if len(drop_window) == 60 and sum(drop_window) > int(
                        60 * MAX_DROP_RATIO
                    ):
                        logger.warning(
                            "Disconnecting slow client",
                            extra={
                                "match_id": match_id,
                                "drops": sum(drop_window),
                            },
                        )
                        break
                    continue  # skip data message for this frame too
                except Exception:
                    break

                # Send data at 10Hz (every DATA_INTERVAL frames)
                if i % DATA_INTERVAL == 0 and replay.data_entries:
                    found = _find_nearest_entry(
                        replay.data_entries, i + 1, data_cursor
                    )
                    if found is not None:
                        entry, data_cursor = found
                        msg = _translate_data_entry(match_id, entry)
                        try:
                            await asyncio.wait_for(
                                websocket.send_text(json.dumps(msg)),
                                timeout=SEND_TIMEOUT,
                            )
                        except (asyncio.TimeoutError, Exception):
                            pass  # data message drops are non-fatal

                # Drift-corrected pacing
                target_time = stream_start + (i + 1) / REPLAY_FPS
                sleep_time = target_time - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            # Send end signal
            if not disconnected.is_set():
                try:
                    await websocket.send_text(json.dumps({"status": "ended"}))
                except Exception:
                    pass

        finally:
            watcher.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        async with _ip_lock:
            _ip_stream_count[client_ip] = max(0, _ip_stream_count[client_ip] - 1)
            _global_stream_count = max(0, _global_stream_count - 1)
