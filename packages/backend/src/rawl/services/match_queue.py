"""Elo-proximity matchmaking queue using Redis sorted sets.

Each game_id gets a sorted set keyed ``matchqueue:{game_id}`` where the
score is the fighter's Elo rating.  The scheduler scans each set and
pairs fighters within an Elo window that widens by 50 every tick.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

QUEUE_KEY_PREFIX = "matchqueue"
META_KEY_PREFIX = "matchqueue:meta"
ELO_WINDOW_BASE = 200
ELO_WINDOW_STEP = 50


def _queue_key(game_id: str) -> str:
    return f"{QUEUE_KEY_PREFIX}:{game_id}"


def _meta_key(fighter_id: str) -> str:
    return f"{META_KEY_PREFIX}:{fighter_id}"


async def enqueue_fighter(
    fighter_id: uuid.UUID,
    game_id: str,
    match_type: str,
    elo_rating: float,
    owner_id: str,
) -> bool:
    """Add a fighter to the Redis sorted-set matchmaking queue."""
    fid = str(fighter_id)
    pipe = redis_pool.pipeline()
    pipe.zadd(_queue_key(game_id), {fid: elo_rating})
    pipe.set(
        _meta_key(fid),
        json.dumps({
            "game_id": game_id,
            "match_type": match_type,
            "owner_id": owner_id,
            "enqueued_at": time.time(),
            "ticks": 0,
        }),
        ex=3600,
    )
    await pipe.execute()
    logger.info(
        "Fighter enqueued",
        extra={"fighter_id": fid, "game_id": game_id, "elo": elo_rating},
    )
    return True


async def dequeue_fighter(fighter_id: uuid.UUID, game_id: str) -> None:
    """Remove a fighter from the queue."""
    fid = str(fighter_id)
    pipe = redis_pool.pipeline()
    pipe.zrem(_queue_key(game_id), fid)
    pipe.delete(_meta_key(fid))
    await pipe.execute()


async def get_active_game_ids() -> list[str]:
    """Return game_ids that have queued fighters."""
    cursor, keys = await redis_pool.scan(
        cursor=0, match=f"{QUEUE_KEY_PREFIX}:*", count=100
    )
    game_ids: list[str] = []
    all_keys = list(keys)
    while cursor:
        cursor, keys = await redis_pool.scan(
            cursor=cursor, match=f"{QUEUE_KEY_PREFIX}:*", count=100
        )
        all_keys.extend(keys)
    for key in all_keys:
        k = key if isinstance(key, str) else key.decode()
        if k.startswith(META_KEY_PREFIX):
            continue
        game_ids.append(k.split(":", 1)[1])
    return game_ids


async def try_match(game_id: str) -> tuple[str, str] | None:
    """Attempt to pair two fighters from the queue by Elo proximity.

    Uses ZRANGEBYSCORE within ``ELO_WINDOW_BASE + ticks * ELO_WINDOW_STEP``
    for each candidate.  Enforces self-matching prohibition via owner_id.
    Returns ``(fighter_a_id, fighter_b_id)`` or ``None``.
    """
    qkey = _queue_key(game_id)
    members = await redis_pool.zrange(qkey, 0, -1, withscores=True)
    if len(members) < 2:
        return None

    for member_a, elo_a in members:
        fid_a = member_a if isinstance(member_a, str) else member_a.decode()
        meta_raw_a = await redis_pool.get(_meta_key(fid_a))
        if not meta_raw_a:
            await redis_pool.zrem(qkey, fid_a)
            continue
        meta_a = json.loads(meta_raw_a)
        ticks_a = meta_a.get("ticks", 0)
        window = ELO_WINDOW_BASE + ticks_a * ELO_WINDOW_STEP

        candidates = await redis_pool.zrangebyscore(
            qkey, elo_a - window, elo_a + window, withscores=True
        )
        for member_b, _elo_b in candidates:
            fid_b = member_b if isinstance(member_b, str) else member_b.decode()
            if fid_b == fid_a:
                continue
            meta_raw_b = await redis_pool.get(_meta_key(fid_b))
            if not meta_raw_b:
                await redis_pool.zrem(qkey, fid_b)
                continue
            meta_b = json.loads(meta_raw_b)
            if meta_a["owner_id"] == meta_b["owner_id"]:
                continue

            # Valid pair — atomically verify and remove both
            removed = await redis_pool.atomic_pair_remove(qkey, fid_a, fid_b)
            if not removed:
                # One member was already taken by another worker, retry
                continue
            # Clean up metadata keys (have TTL anyway)
            await redis_pool.delete(_meta_key(fid_a), _meta_key(fid_b))
            logger.info(
                "Match paired",
                extra={"fighter_a": fid_a, "fighter_b": fid_b, "game_id": game_id},
            )
            return fid_a, fid_b

    return None


async def widen_windows(game_id: str) -> None:
    """Increment tick counter for all queued fighters (widens Elo window)."""
    qkey = _queue_key(game_id)
    members = await redis_pool.zrange(qkey, 0, -1)
    for member in members:
        fid = member if isinstance(member, str) else member.decode()
        meta_raw = await redis_pool.get(_meta_key(fid))
        if not meta_raw:
            continue
        meta = json.loads(meta_raw)
        meta["ticks"] = meta.get("ticks", 0) + 1
        await redis_pool.set(_meta_key(fid), json.dumps(meta), ex=3600)
