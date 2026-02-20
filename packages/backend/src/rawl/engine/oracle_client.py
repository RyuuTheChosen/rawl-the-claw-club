from __future__ import annotations

import asyncio
import logging

from rawl.config import settings

logger = logging.getLogger(__name__)

SETTLE_TIMEOUT = 60  # seconds; covers 3 retries + backoffs [1,2,4]s with headroom


class OracleClient:
    """Client for submitting match results to Base smart contract.

    Handles signing and submitting lock_match, resolve_match, and cancel_match
    transactions using the oracle keypair via the EVMClient.
    """

    async def submit_lock(self, match_id: str) -> str | None:
        """Submit lock_match transaction. Returns tx hash or None on failure."""
        try:
            return await asyncio.wait_for(
                self._submit_lock_inner(match_id),
                timeout=SETTLE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("lockMatch RPC timed out", extra={"match_id": match_id})
            return None

    async def submit_resolve(self, match_id: str, winner: str, match_hash: str) -> str | None:
        """Submit resolve_match transaction.

        Args:
            match_id: UUID string
            winner: "P1" or "P2"
            match_hash: SHA-256 hex string of match result (log-only, not passed to chain)
        """
        try:
            return await asyncio.wait_for(
                self._submit_resolve_inner(match_id, winner, match_hash),
                timeout=SETTLE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("resolveMatch RPC timed out", extra={"match_id": match_id})
            return None

    async def submit_cancel(self, match_id: str, reason: str = "engine_failure") -> str | None:
        """Submit cancel_match transaction. Returns tx hash or None on failure."""
        try:
            return await asyncio.wait_for(
                self._submit_cancel_inner(match_id, reason),
                timeout=SETTLE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("cancelMatch RPC timed out", extra={"match_id": match_id})
            return None

    async def _submit_lock_inner(self, match_id: str) -> str | None:
        from rawl.evm.client import evm_client

        logger.info("Submitting lock_match", extra={"match_id": match_id})
        return await self._retry(
            lambda: evm_client.lock_match_on_chain(match_id),
            "lock_match",
            match_id,
        )

    async def _submit_resolve_inner(
        self, match_id: str, winner: str, match_hash: str
    ) -> str | None:
        from rawl.evm.client import evm_client

        # Convert "P1"/"P2" to contract u8 (0=SideA, 1=SideB)
        winner_u8 = 0 if winner == "P1" else 1

        logger.info(
            "Submitting resolve_match",
            extra={"match_id": match_id, "winner": winner, "hash": match_hash[:16]},
        )
        return await self._retry(
            lambda: evm_client.resolve_match_on_chain(match_id, winner_u8),
            "resolve_match",
            match_id,
        )

    async def _submit_cancel_inner(self, match_id: str, reason: str) -> str | None:
        from rawl.evm.client import evm_client

        logger.info(
            "Submitting cancel_match",
            extra={"match_id": match_id, "reason": reason},
        )
        return await self._retry(
            lambda: evm_client.cancel_match_on_chain(match_id),
            "cancel_match",
            match_id,
        )

    async def _retry(self, fn, instruction_name: str, match_id: str) -> str | None:
        """Retry with backoff [1, 2, 4]s up to base_max_retries."""
        backoff = [1, 2, 4]
        for attempt in range(settings.base_max_retries):
            try:
                return await fn()
            except Exception as e:
                logger.warning(
                    f"Oracle {instruction_name} attempt {attempt + 1} failed",
                    extra={"match_id": match_id, "error": str(e)},
                )
                if attempt < settings.base_max_retries - 1 and attempt < len(backoff):
                    await asyncio.sleep(backoff[attempt])
        logger.error(
            f"Oracle {instruction_name} failed after {settings.base_max_retries} retries",
            extra={"match_id": match_id},
        )
        return None


oracle_client = OracleClient()
