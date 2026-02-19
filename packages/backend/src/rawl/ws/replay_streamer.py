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
from collections import defaultdict
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rawl.s3_client import download_bytes

logger = logging.getLogger(__name__)

replay_router = APIRouter()

# ─── Replay data container ───────────────────────────────────────────────────

@dataclass(frozen=True)
class _ReplayData:
    mjpeg: bytes
    offsets: list[int]
    data_entries: list[dict]
    num_frames: int
    size_bytes: int

    def extract_frame(self, index: int) -> bytes:
        """Extract single JPEG frame by index. O(1) via offset lookup."""
        if index < 0 or index >= self.num_frames:
            raise IndexError(f"Frame {index} out of range [0, {self.num_frames})")
        start = self.offsets[index]
        end = self.offsets[index + 1] if index + 1 < self.num_frames else len(self.mjpeg)
        return self.mjpeg[start:end]


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
        async with self._global_lock:
            if match_id not in self._locks:
                self._locks[match_id] = asyncio.Lock()
            lock = self._locks[match_id]

        async with lock:
            if match_id in self._cache:
                data, _ = self._cache[match_id]
                self._cache[match_id] = (data, time.monotonic())
                return data

            replay = await self._download(match_id)
            if replay is None:
                return None

            self._evict_if_needed()
            self._cache[match_id] = (replay, time.monotonic())
            return replay

    async def _download(self, match_id: str) -> _ReplayData | None:
        """Download all 3 replay files from S3 and parse."""
        mjpeg = await download_bytes(f"replays/{match_id}.mjpeg")
        idx_bytes = await download_bytes(f"replays/{match_id}.idx")
        json_bytes = await download_bytes(f"replays/{match_id}.json")

        if not mjpeg or not idx_bytes or not json_bytes:
            logger.error("Failed to download replay files", extra={"match_id": match_id})
            return None

        # Parse index (u64 LE offsets)
        num_frames = len(idx_bytes) // 8
        offsets = list(struct.unpack(f"<{num_frames}Q", idx_bytes))

        # Validate offsets are monotonically increasing and within bounds
        for i, offset in enumerate(offsets):
            if offset >= len(mjpeg):
                logger.error(
                    "Corrupt index: offset beyond MJPEG",
                    extra={"frame": i, "offset": offset},
                )
                return None
            if i > 0 and offset <= offsets[i - 1]:
                logger.error("Corrupt index: non-monotonic offset", extra={"frame": i})
                return None

        # Parse data sidecar
        try:
            data_entries = json.loads(json_bytes)
        except json.JSONDecodeError:
            logger.error("Corrupt JSON sidecar", extra={"match_id": match_id})
            return None

        return _ReplayData(
            mjpeg=mjpeg,
            offsets=offsets,
            data_entries=data_entries,
            num_frames=num_frames,
            size_bytes=len(mjpeg) + len(idx_bytes) + len(json_bytes),
        )

    def _evict_if_needed(self) -> None:
        """Evict oldest entry if cache is full. Also evict expired entries."""
        now = time.monotonic()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > _CACHE_TTL_SECONDS]
        for k in expired:
            del self._cache[k]

        while len(self._cache) >= _MAX_CACHE_ENTRIES:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]


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

REPLAY_FPS = 60
DATA_INTERVAL = 6  # Send data every 6th frame (=10Hz at 60fps)


@replay_router.websocket("/replay/{match_id}")
async def replay_endpoint(websocket: WebSocket, match_id: str) -> None:
    global _global_stream_count

    # Validate match_id is a UUID
    try:
        _uuid.UUID(match_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid match_id")
        return

    # Connection limits
    client_ip = _get_client_ip(websocket)
    if _ip_stream_count[client_ip] >= _MAX_STREAMS_PER_IP:
        await websocket.close(code=4029, reason="Too many replay streams")
        return
    if _global_stream_count >= _MAX_GLOBAL_STREAMS:
        await websocket.close(code=4029, reason="Server at replay capacity")
        return

    # Accept connection
    await websocket.accept()
    _ip_stream_count[client_ip] += 1
    _global_stream_count += 1

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

        # Stream frames at 60fps with drift correction
        stream_start = time.monotonic()
        data_cursor = 0

        try:
            for i in range(replay.num_frames):
                if disconnected.is_set():
                    break

                # Extract and send frame
                frame_bytes = replay.extract_frame(i)
                try:
                    await websocket.send_bytes(frame_bytes)
                except Exception:
                    break

                # Send data at 10Hz (every DATA_INTERVAL frames)
                if i % DATA_INTERVAL == 0 and replay.data_entries:
                    found = _find_nearest_entry(replay.data_entries, i + 1, data_cursor)
                    if found is not None:
                        entry, data_cursor = found
                        msg = _translate_data_entry(match_id, entry)
                        try:
                            await websocket.send_text(json.dumps(msg))
                        except Exception:
                            break

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
        _ip_stream_count[client_ip] = max(0, _ip_stream_count[client_ip] - 1)
        _global_stream_count = max(0, _global_stream_count - 1)
