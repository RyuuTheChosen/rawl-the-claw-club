from __future__ import annotations

import asyncio
import json
import logging
import struct
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

# Binary WS protocol: header = type(1) + timestamp_us(8 BE) + seq(4 BE) = 13 bytes
TYPE_SEQ_HEADER = 0x01
TYPE_KEYFRAME = 0x02
TYPE_DELTA = 0x03
TYPE_EOS = 0x04
HEADER_SIZE = 13

# Backpressure: disconnect if > 80% frames dropped in this window
_BACKPRESSURE_WINDOW = 60
_BACKPRESSURE_DROP_THRESHOLD = 0.80


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


def _build_ws_frame(
    frame_type: int, timestamp_us: int, seq: int, nal_data: bytes = b""
) -> bytes:
    """Build binary WebSocket frame: type(1) + timestamp(8 BE) + seq(4 BE) + NAL data."""
    header = struct.pack(">BQI", frame_type, timestamp_us, seq)
    return header + nal_data


def _nal_type_to_ws_type(nal_type: bytes) -> int:
    """Map Redis NAL type tag to WS protocol type byte."""
    if nal_type == b"seq":
        return TYPE_SEQ_HEADER
    elif nal_type == b"key":
        return TYPE_KEYFRAME
    elif nal_type == b"delta":
        return TYPE_DELTA
    elif nal_type == b"eos":
        return TYPE_EOS
    return TYPE_DELTA


async def _find_latest_keyframe_id(stream_key: str) -> str | None:
    """Find the stream ID of the most recent keyframe using XREVRANGE.

    Returns the stream ID to start reading from, or None if no keyframe found.
    """
    try:
        entries = await redis_pool.stream_revrange(stream_key, count=60)
        for msg_id, data in entries:
            nal_type = data.get(b"type", b"")
            if nal_type in (b"key", b"seq"):
                return msg_id.decode() if isinstance(msg_id, bytes) else msg_id
    except Exception as e:
        logger.debug("Failed to find latest keyframe", extra={"error": str(e)})
    return None


@ws_router.websocket("/match/{match_id}/video")
async def video_channel(websocket: WebSocket, match_id: str) -> None:
    """Binary WebSocket channel streaming H.264 NAL units.

    Protocol (per message):
      Byte 0:    type (0x01=seq, 0x02=keyframe, 0x03=delta, 0x04=EOS)
      Bytes 1-8: timestamp microseconds (uint64 BE)
      Bytes 9-12: sequence number (uint32 BE)
      Bytes 13+: H.264 NAL unit data (Annex B format)

    Late joiners receive SPS+PPS + latest keyframe on connect.
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
    sps_pps_key = f"match:{match_id}:sps_pps"

    # Late joiner: send SPS+PPS first, then seek to latest keyframe
    last_id = "$"
    try:
        # Send cached SPS+PPS if available
        sps_pps = await redis_pool.get(sps_pps_key)
        if sps_pps:
            frame = _build_ws_frame(TYPE_SEQ_HEADER, 0, 0, sps_pps)
            await websocket.send_bytes(frame)

        # Find latest keyframe to start from
        keyframe_id = await _find_latest_keyframe_id(stream_key)
        if keyframe_id:
            # Read from just before the keyframe (the keyframe entry itself)
            # XREAD uses exclusive lower bound, so decrement the ID
            parts = keyframe_id.split("-")
            if len(parts) == 2:
                ts_part, seq_part = parts
                if int(seq_part) > 0:
                    last_id = f"{ts_part}-{int(seq_part) - 1}"
                else:
                    last_id = f"{int(ts_part) - 1}-99999"
    except Exception as e:
        logger.debug("Late joiner setup failed, starting from live", extra={"error": str(e)})

    # Backpressure tracking
    sent_count = 0
    dropped_count = 0

    try:
        while not disconnected.is_set():
            try:
                messages = await redis_pool.stream_read(
                    stream_key, last_id=last_id, count=10, block=16
                )
            except Exception as e:
                logger.warning(
                    "Redis stream read error (video)",
                    extra={"match_id": match_id, "error": str(e)},
                )
                await asyncio.sleep(0.1)
                continue

            if not messages:
                continue

            # Collect all entries from this batch
            entries_to_send: list[tuple[str, dict]] = []
            for _stream_name, entries in messages:
                for msg_id, data in entries:
                    last_id = msg_id
                    entries_to_send.append((msg_id, data))

            if not entries_to_send:
                continue

            # Keyframe-aware skip: when behind, keep latest keyframe + all deltas after it
            if len(entries_to_send) > 3:
                last_keyframe_idx = -1
                for i, (_mid, d) in enumerate(entries_to_send):
                    if d.get(b"type") in (b"key", b"seq", b"eos"):
                        last_keyframe_idx = i
                if last_keyframe_idx > 0:
                    entries_to_send = entries_to_send[last_keyframe_idx:]

            for _msg_id, data in entries_to_send:
                nal_type = data.get(b"type", b"delta")

                # EOS sentinel
                if nal_type == b"eos":
                    eos_frame = _build_ws_frame(TYPE_EOS, 0, 0)
                    try:
                        await websocket.send_bytes(eos_frame)
                    except Exception:
                        pass
                    try:
                        await websocket.close(code=1000, reason="Stream ended")
                    except Exception:
                        pass
                    return

                nal_data = data.get(b"nal", b"")
                if not nal_data:
                    continue

                ts = int(data.get(b"ts", b"0"))
                seq = int(data.get(b"seq", b"0"))
                ws_type = _nal_type_to_ws_type(nal_type)
                frame = _build_ws_frame(ws_type, ts, seq, nal_data)

                try:
                    await asyncio.wait_for(websocket.send_bytes(frame), timeout=0.05)
                    sent_count += 1
                except asyncio.TimeoutError:
                    dropped_count += 1
                    # Check backpressure: too many drops → disconnect
                    total = sent_count + dropped_count
                    if total >= _BACKPRESSURE_WINDOW:
                        drop_rate = dropped_count / total
                        if drop_rate > _BACKPRESSURE_DROP_THRESHOLD:
                            logger.warning(
                                "Client too slow, disconnecting",
                                extra={
                                    "match_id": match_id,
                                    "drop_rate": f"{drop_rate:.0%}",
                                },
                            )
                            try:
                                await websocket.close(code=4008, reason="Client too slow")
                            except Exception:
                                pass
                            return
                        # Reset counters for next window
                        sent_count = 0
                        dropped_count = 0
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
