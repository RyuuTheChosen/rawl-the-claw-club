from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

training_ws_router = APIRouter()


@training_ws_router.websocket("/training/{job_id}")
async def training_progress(websocket: WebSocket, job_id: str) -> None:
    """WebSocket for training job progress updates."""
    await websocket.accept()

    stream_key = f"training:{job_id}:progress"
    last_id = "0"

    try:
        while True:
            try:
                messages = await redis_pool.stream_read(
                    stream_key, last_id=last_id, count=5, block=2000
                )
            except Exception:
                await asyncio.sleep(0.5)
                continue

            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    last_id = msg_id
                    decoded = {
                        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                        for k, v in data.items()
                    }
                    await websocket.send_text(json.dumps(decoded))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Training WebSocket error", extra={"job_id": job_id})
