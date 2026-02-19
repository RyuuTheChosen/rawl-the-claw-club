from __future__ import annotations

import asyncio
import json
import logging
import uuid as _uuid
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rawl.monitoring.metrics import ws_connections
from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

ws_router = APIRouter()

# Connection limits per IP
VIDEO_CONNECTIONS_PER_IP = 2
DATA_CONNECTIONS_PER_IP = 5

# Track connections per IP per channel
_video_connections: dict[str, set[WebSocket]] = defaultdict(set)
_data_connections: dict[str, set[WebSocket]] = defaultdict(set)
_ip_video_count: dict[str, int] = defaultdict(int)
_ip_data_count: dict[str, int] = defaultdict(int)


def _get_client_ip(websocket: WebSocket) -> str:
    """Extract client IP from WebSocket connection."""
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = websocket.client
    return client.host if client else "unknown"


async def _watch_disconnect(websocket: WebSocket, event: asyncio.Event) -> None:
    """Wait for a client disconnect and signal the event."""
    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
    except Exception:
        pass
    event.set()


@ws_router.websocket("/match/{match_id}/video")
async def video_channel(websocket: WebSocket, match_id: str) -> None:
    """Binary WebSocket channel streaming JPEG frames at 60fps.

    Each message = raw JPEG bytes (10-30 KB at 256x256), no JSON wrapper.
    Connection limit: 2 concurrent per IP.
    """
    try:
        _uuid.UUID(match_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid match_id format")
        return

    client_ip = _get_client_ip(websocket)

    if _ip_video_count[client_ip] >= VIDEO_CONNECTIONS_PER_IP:
        await websocket.close(code=4029, reason="Too many video connections")
        return

    await websocket.accept()
    _video_connections[match_id].add(websocket)
    _ip_video_count[client_ip] += 1
    ws_connections.labels(channel="video").inc()

    logger.info(
        "Video WebSocket connected",
        extra={"match_id": match_id, "client_ip": client_ip},
    )

    disconnected = asyncio.Event()
    watcher = asyncio.create_task(_watch_disconnect(websocket, disconnected))

    stream_key = f"match:{match_id}:video"
    last_id = "$"  # Only new messages

    try:
        while not disconnected.is_set():
            try:
                # Read a large batch to skip intermediate frames and catch up
                messages = await redis_pool.stream_read(
                    stream_key, last_id=last_id, count=10, block=16
                )
            except Exception as e:
                logger.warning("Redis stream read error (video)", extra={"match_id": match_id, "error": str(e)})
                await asyncio.sleep(0.1)
                continue

            if not messages:
                continue

            latest_frame = b""
            for stream_name, entries in messages:
                for msg_id, data in entries:
                    last_id = msg_id
                    latest_frame = data.get(b"frame", b"")
            # Only send the last (most recent) frame from this batch
            if latest_frame:
                try:
                    await websocket.send_bytes(latest_frame)
                except Exception:
                    return
    except WebSocketDisconnect:
        pass
    finally:
        watcher.cancel()
        _video_connections[match_id].discard(websocket)
        _ip_video_count[client_ip] = max(0, _ip_video_count[client_ip] - 1)
        ws_connections.labels(channel="video").dec()
        logger.info(
            "Video WebSocket disconnected",
            extra={"match_id": match_id, "client_ip": client_ip},
        )


@ws_router.websocket("/match/{match_id}/data")
async def data_channel(websocket: WebSocket, match_id: str) -> None:
    """JSON WebSocket channel at 10Hz with all 16 fields per SDD Section 8.3.

    Fields: match_id, timestamp, health_a, health_b, round, timer, status,
    round_winner, match_winner, team_health_a, team_health_b,
    active_char_a, active_char_b, odds_a, odds_b, pool_total.

    Connection limit: 5 concurrent per IP.
    """
    try:
        _uuid.UUID(match_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid match_id format")
        return

    client_ip = _get_client_ip(websocket)

    if _ip_data_count[client_ip] >= DATA_CONNECTIONS_PER_IP:
        await websocket.close(code=4029, reason="Too many data connections")
        return

    await websocket.accept()
    _data_connections[match_id].add(websocket)
    _ip_data_count[client_ip] += 1
    ws_connections.labels(channel="data").inc()

    logger.info(
        "Data WebSocket connected",
        extra={"match_id": match_id, "client_ip": client_ip},
    )

    disconnected = asyncio.Event()
    watcher = asyncio.create_task(_watch_disconnect(websocket, disconnected))

    stream_key = f"match:{match_id}:data"
    last_id = "$"

    try:
        while not disconnected.is_set():
            try:
                messages = await redis_pool.stream_read(
                    stream_key, last_id=last_id, count=1, block=200
                )
            except Exception as e:
                logger.warning("Redis stream read error (data)", extra={"match_id": match_id, "error": str(e)})
                await asyncio.sleep(0.1)
                continue

            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    last_id = msg_id

                    # Build the 16-field data message
                    msg = _build_data_message(match_id, data)
                    try:
                        await websocket.send_text(json.dumps(msg))
                    except Exception:
                        return
    except WebSocketDisconnect:
        pass
    finally:
        watcher.cancel()
        _data_connections[match_id].discard(websocket)
        _ip_data_count[client_ip] = max(0, _ip_data_count[client_ip] - 1)
        ws_connections.labels(channel="data").dec()
        logger.info(
            "Data WebSocket disconnected",
            extra={"match_id": match_id, "client_ip": client_ip},
        )


def _build_data_message(match_id: str, raw_data: dict) -> dict:
    """Build the 16-field data channel message from Redis stream data."""

    def _get(key: str, default=None):
        val = raw_data.get(key.encode(), raw_data.get(key, default))
        if isinstance(val, bytes):
            val = val.decode()
        return val

    return {
        "match_id": match_id,
        "timestamp": _get("timestamp", ""),
        "health_a": _safe_float(_get("p1_health", 0)) or 0,
        "health_b": _safe_float(_get("p2_health", 0)) or 0,
        "round": _safe_int(_get("round_number", 0)),
        "timer": _safe_int(_get("timer", 0)),
        "status": _get("status", "live"),
        "round_winner": _safe_int_or_none(_get("round_winner")),
        "match_winner": _safe_int_or_none(_get("match_winner")),
        "team_health_a": _get("p1_team_health"),
        "team_health_b": _get("p2_team_health"),
        "active_char_a": _get("p1_active_character"),
        "active_char_b": _get("p2_active_character"),
        "has_round_timer": bool(_safe_int(_get("has_round_timer", 1))),
        "odds_a": _safe_float(_get("odds_a")) or 0,
        "odds_b": _safe_float(_get("odds_b")) or 0,
        "pool_total": _safe_float(_get("pool_total")) or 0,
    }


def _safe_int_or_none(val) -> int | None:
    if val is None or val == "" or val == "None":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
