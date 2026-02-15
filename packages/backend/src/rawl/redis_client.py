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
            raise RuntimeError("Redis pool not initialized. Call initialize() first.")
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.aclose()
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


redis_pool = RedisPool()
