"""Emulation job queue interface.

Ranked matches flow through a deferred sorted set (for the betting window).
Calibration and immediate custom matches go directly to the list queues.

Redis data structures:
  rawl:emulation:ready          sorted set  score=run_at_unix  member=job_id
  rawl:emulation:jobs           hash        key=job_id         value=JSON payload
  rawl:emulation:queue          list        ranked matches ready to run now (FIFO)
  rawl:emulation:queue:cal      list        calibration matches ready to run now
  rawl:emulation:processing     list        ranked jobs currently being processed
  rawl:emulation:processing:cal list        calibration jobs currently being processed
"""
from __future__ import annotations

import json
import time

from rawl.redis_client import redis_pool

READY_ZSET   = "rawl:emulation:ready"
JOBS_HASH    = "rawl:emulation:jobs"
RANKED_QUEUE = "rawl:emulation:queue"
CAL_QUEUE    = "rawl:emulation:queue:cal"

# Atomically move ready deferred jobs into active queues.
# KEYS[1]=ready zset  KEYS[2]=jobs hash  KEYS[3]=ranked queue  KEYS[4]=cal queue
# ARGV[1]=current unix timestamp (float string)
_PROMOTE_LUA = """
local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 20)
local promoted = 0
for _, id in ipairs(ids) do
    local payload = redis.call('HGET', KEYS[2], id)
    if payload then
        local ok, job = pcall(cjson.decode, payload)
        if ok then
            local q = job.calibration and KEYS[4] or KEYS[3]
            redis.call('RPUSH', q, payload)
            redis.call('HDEL', KEYS[2], id)
        end
    end
    redis.call('ZREM', KEYS[1], id)
    promoted = promoted + 1
end
return promoted
"""


async def enqueue_ranked(
    match_id: str,
    game_id: str,
    model_a: str,
    model_b: str,
    match_format: int,
    delay_seconds: float,
) -> None:
    """Enqueue a ranked match to the deferred sorted set (betting window)."""
    payload = json.dumps({
        "job_type": "match",
        "match_id": match_id,
        "game_id": game_id,
        "fighter_a_model": model_a,
        "fighter_b_model": model_b,
        "match_format": match_format,
        "calibration": False,
    })
    run_at = time.time() + delay_seconds
    r = redis_pool.client
    await r.hset(JOBS_HASH, match_id, payload)
    await r.zadd(READY_ZSET, {match_id: run_at})


async def enqueue_ranked_now(
    match_id: str,
    game_id: str,
    model_a: str,
    model_b: str,
    match_format: int,
) -> None:
    """Enqueue a ranked match for immediate execution (no betting window)."""
    payload = json.dumps({
        "job_type": "match",
        "match_id": match_id,
        "game_id": game_id,
        "fighter_a_model": model_a,
        "fighter_b_model": model_b,
        "match_format": match_format,
        "calibration": False,
    })
    await redis_pool.client.rpush(RANKED_QUEUE, payload)


async def enqueue_calibration_now(fighter_id: str) -> None:
    """Enqueue a calibration job for immediate execution."""
    payload = json.dumps({"job_type": "calibration", "fighter_id": fighter_id})
    await redis_pool.client.rpush(CAL_QUEUE, payload)


async def promote_ready() -> int:
    """Atomic promotion of ready deferred jobs to active queues.

    Returns the number of jobs promoted. Safe to call from multiple ARQ workers
    concurrently — the Lua script is atomic.
    """
    r = redis_pool.client
    now = str(time.time())
    result = await r.eval(_PROMOTE_LUA, 4, READY_ZSET, JOBS_HASH, RANKED_QUEUE, CAL_QUEUE, now)
    return int(result)
