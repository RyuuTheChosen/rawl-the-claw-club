"""Lock-based sequential nonce manager for EVM transactions.

EVM requires strictly sequential nonces (unlike Solana's stateless blockhashes).
This manager tracks the local nonce and uses an asyncio.Lock to prevent races
when multiple coroutines submit transactions concurrently.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class NonceManager:
    def __init__(self, w3, address: str):
        self._w3 = w3
        self._address = address
        self._lock = asyncio.Lock()
        self._local_nonce: int | None = None

    async def get_nonce(self) -> int:
        """Return the next nonce, fetching from chain on first call."""
        async with self._lock:
            if self._local_nonce is None:
                self._local_nonce = await self._w3.eth.get_transaction_count(
                    self._address, "pending"
                )
            else:
                self._local_nonce += 1
            return self._local_nonce

    async def reset(self):
        """Reset local nonce — next get_nonce() will re-fetch from chain."""
        async with self._lock:
            self._local_nonce = None

    async def rollback(self):
        """Decrement nonce after a failed send (nonce was consumed but tx didn't land)."""
        async with self._lock:
            if self._local_nonce is not None and self._local_nonce > 0:
                self._local_nonce -= 1
