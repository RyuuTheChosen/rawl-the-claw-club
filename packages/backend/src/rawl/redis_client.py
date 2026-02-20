from __future__ import annotations

import redis.asyncio as aioredis

from rawl.config import settings


class RedisPool:
    def __init__(self) -> None:
        self._pool: aioredis.Redis | None = None

    async def initialize(self) -> None:
        self._pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,
            max_connections=20,
        )

    @property
    def client(self) -> aioredis.Redis:
        if self._pool is None:
            # Auto-initialize on first access (from_url is synchronous)
            self._pool = aioredis.from_url(
                settings.redis_url,
                decode_responses=False,
                max_connections=20,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    def reset(self) -> None:
        """Drop the cached client without closing.

        The old connection's event loop is dead, so we can't await aclose().
        Just dereference it and let the next .client access create a fresh one
        on the current event loop.
        """
        self._pool = None

    # --- Stream helpers ---

    async def stream_publish(self, stream: str, data: dict, maxlen: int = 1000) -> str:
        """Publish a message to a Redis stream with MAXLEN trimming."""
        msg_id = await self.client.xadd(stream, data, maxlen=maxlen, approximate=True)
        return msg_id

    async def stream_publish_bytes(self, stream: str, key: str, value: bytes, maxlen: int = 1000) -> str:
        """Publish binary data to a Redis stream."""
        msg_id = await self.client.xadd(stream, {key: value}, maxlen=maxlen, approximate=True)
        return msg_id

    async def stream_read(
        self, stream: str, last_id: str = "0", count: int = 10, block: int = 1000
    ) -> list:
        """Read from a Redis stream with BLOCK."""
        return await self.client.xread({stream: last_id}, count=count, block=block)

    async def stream_revrange(self, stream: str, count: int = 10) -> list:
        """Read entries from a Redis stream in reverse order (newest first)."""
        return await self.client.xrevrange(stream, count=count)

    async def set_with_expiry(self, key: str, value: str, ex: int) -> None:
        """Set a key with expiry in seconds."""
        await self.client.set(key, value, ex=ex)

    async def get(self, key: str) -> bytes | None:
        return await self.client.get(key)

    async def incr(self, key: str) -> int:
        return await self.client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        return await self.client.ttl(key)

    async def ping(self) -> bool:
        """Ping the Redis server to check connectivity."""
        return await self.client.ping()

    async def scan(self, cursor: int = 0, match: str | None = None, count: int | None = None) -> tuple:
        """Scan keys matching a pattern."""
        return await self.client.scan(cursor=cursor, match=match, count=count)

    # --- Sorted set helpers (used by match_queue) ---

    def pipeline(self):
        """Create a Redis pipeline for atomic multi-command execution."""
        return self.client.pipeline()

    async def zadd(self, key: str, mapping: dict, **kwargs):
        """Add members to a sorted set."""
        return await self.client.zadd(key, mapping, **kwargs)

    async def zrange(self, key: str, start: int, end: int, withscores: bool = False, **kwargs):
        """Return a range of members from a sorted set by index."""
        return await self.client.zrange(key, start, end, withscores=withscores, **kwargs)

    async def zrangebyscore(self, key: str, min_score: float, max_score: float, withscores: bool = False, **kwargs):
        """Return members from a sorted set within a score range."""
        return await self.client.zrangebyscore(key, min_score, max_score, withscores=withscores, **kwargs)

    async def zcard(self, key: str) -> int:
        """Return the number of members in a sorted set."""
        return await self.client.zcard(key)

    async def zrem(self, key: str, *members):
        """Remove members from a sorted set."""
        return await self.client.zrem(key, *members)

    async def set(self, key: str, value, **kwargs):
        """Set a key-value pair with optional kwargs (ex, px, etc.)."""
        return await self.client.set(key, value, **kwargs)

    async def delete(self, *keys):
        """Delete one or more keys."""
        return await self.client.delete(*keys)

    # --- Lua script helpers ---

    _RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, ttl)
end
return current
"""

    async def rate_limit_check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Atomic rate limit check. Returns True if request is within limit."""
        count = await self.client.eval(self._RATE_LIMIT_LUA, 1, key, limit, window_seconds)
        return count <= limit

    _ATOMIC_PAIR_REMOVE_LUA = """
local key = KEYS[1]
local a = ARGV[1]
local b = ARGV[2]
if redis.call('ZSCORE', key, a) and redis.call('ZSCORE', key, b) then
    redis.call('ZREM', key, a, b)
    return 1
end
return 0
"""

    async def atomic_pair_remove(self, key: str, member_a: str, member_b: str) -> bool:
        """Atomically verify both members exist in sorted set and remove them.

        Returns True if both were present and removed, False otherwise.
        """
        result = await self.client.eval(self._ATOMIC_PAIR_REMOVE_LUA, 1, key, member_a, member_b)
        return result == 1


redis_pool = RedisPool()
