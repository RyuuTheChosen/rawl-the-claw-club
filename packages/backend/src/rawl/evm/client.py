"""EVM client for Base chain — drop-in replacement for SolanaClient.

Provides the same public API surface: initialize/close/reset lifecycle,
match operations (create/lock/resolve/cancel/timeout), and read operations
(get_match_pool/get_bet/bet_exists).
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from eth_account import Account
from web3 import AsyncWeb3, AsyncHTTPProvider

from rawl.config import settings
from rawl.evm.abi import CONTRACT_ABI
from rawl.evm.nonce_manager import NonceManager
from rawl.monitoring.metrics import chain_tx_total

logger = logging.getLogger(__name__)

BACKOFF = [1, 2, 4]


def match_id_to_bytes(match_id: str) -> bytes:
    """Convert UUID string to 32-byte bytes for contract bytes32 param.

    Same logic as the old Solana pda.match_id_to_bytes():
    UUID hex (16 bytes) + 16 zero bytes = 32 bytes.
    """
    return uuid.UUID(match_id).bytes.ljust(32, b"\x00")


class EVMClient:
    """Drop-in replacement for SolanaClient. Same public API."""

    def __init__(self):
        self._w3: AsyncWeb3 | None = None
        self._oracle: Account | None = None
        self._contract = None
        self._nonce: NonceManager | None = None
        self._initialized = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Load private key, create AsyncWeb3, init NonceManager."""
        self._w3 = AsyncWeb3(AsyncHTTPProvider(settings.base_rpc_url))
        self._oracle = Account.from_key(settings.oracle_private_key)
        self._contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(settings.contract_address),
            abi=CONTRACT_ABI,
        )
        self._nonce = NonceManager(self._w3, self._oracle.address)
        self._initialized = True
        logger.info(
            "EVMClient initialized",
            extra={
                "oracle": self._oracle.address,
                "contract": settings.contract_address,
                "chain_id": settings.base_chain_id,
            },
        )

    async def close(self) -> None:
        """Close HTTP session."""
        self._w3 = None
        self._contract = None
        self._nonce = None
        self._initialized = False

    def reset(self) -> None:
        """SYNC — drop refs without awaiting close (for subprocess workers).

        Called before asyncio.run() when the old event loop is dead.
        """
        self._w3 = None
        self._contract = None
        self._nonce = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazy-init for workers without a lifespan."""
        if not self._initialized:
            await self.initialize()

    # ── Health ──

    async def get_health(self) -> bool:
        """Check if the RPC node is reachable."""
        await self._ensure_initialized()
        return await self._w3.is_connected()

    # ── Internal: transaction building ──

    async def _get_base_fee(self) -> int:
        latest = await self._w3.eth.get_block("latest")
        return latest.get("baseFeePerGas", 0)

    async def _get_revert_reason(self, tx_hash, receipt) -> str:
        try:
            tx = await self._w3.eth.get_transaction(tx_hash)
            await self._w3.eth.call(
                {"from": tx["from"], "to": tx["to"], "data": tx["input"], "value": tx["value"]},
                block_identifier=receipt["blockNumber"] - 1,
            )
            return "Unknown revert"
        except Exception as e:
            return str(e)

    async def _send_tx(self, fn_call, instruction_name: str) -> str:
        """Build, sign, send, and confirm a contract transaction with retry."""
        await self._ensure_initialized()

        last_error = None
        for attempt in range(settings.base_max_retries):
            try:
                nonce = await self._nonce.get_nonce()
                base_fee = await self._get_base_fee()
                priority_fee = self._w3.to_wei("0.001", "gwei")

                tx = await fn_call.build_transaction(
                    {
                        "from": self._oracle.address,
                        "nonce": nonce,
                        "chainId": settings.base_chain_id,
                        "maxPriorityFeePerGas": priority_fee,
                        "maxFeePerGas": base_fee * 2 + priority_fee,
                    }
                )
                tx["gas"] = await self._w3.eth.estimate_gas(tx)

                signed = self._oracle.sign_transaction(tx)
                tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = await self._w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=settings.base_confirm_timeout
                )

                if receipt["status"] != 1:
                    reason = await self._get_revert_reason(tx_hash, receipt)
                    raise RuntimeError(f"{instruction_name} reverted: {reason}")

                chain_tx_total.labels(instruction=instruction_name, status="success").inc()
                return tx_hash.hex()

            except RuntimeError:
                raise  # Don't retry contract reverts

            except Exception as e:
                if "nonce too low" in str(e).lower():
                    await self._nonce.reset()
                else:
                    await self._nonce.rollback()

                if attempt < len(BACKOFF) - 1:
                    await asyncio.sleep(BACKOFF[attempt])
                last_error = e

        chain_tx_total.labels(instruction=instruction_name, status="failure").inc()
        raise RuntimeError(
            f"{instruction_name} failed after {settings.base_max_retries} retries: {last_error}"
        )

    # ── Match operations (return tx hash hex string) ──

    async def create_match_on_chain(
        self, match_id: str, fighter_a: str, fighter_b: str
    ) -> str:
        await self._ensure_initialized()
        mid = match_id_to_bytes(match_id)
        fn = self._contract.functions.createMatch(
            mid,
            self._w3.to_checksum_address(fighter_a),
            self._w3.to_checksum_address(fighter_b),
            self._w3.to_wei("0.001", "ether"),  # default minBet
            0,  # no betting window limit
        )
        return await self._send_tx(fn, "create_match")

    async def lock_match_on_chain(self, match_id: str) -> str:
        await self._ensure_initialized()
        fn = self._contract.functions.lockMatch(match_id_to_bytes(match_id))
        return await self._send_tx(fn, "lock_match")

    async def resolve_match_on_chain(self, match_id: str, winner: int) -> str:
        """Resolve match. winner: 0=SideA, 1=SideB."""
        await self._ensure_initialized()
        fn = self._contract.functions.resolveMatch(match_id_to_bytes(match_id), winner)
        return await self._send_tx(fn, "resolve_match")

    async def cancel_match_on_chain(self, match_id: str) -> str:
        await self._ensure_initialized()
        fn = self._contract.functions.cancelMatch(match_id_to_bytes(match_id))
        return await self._send_tx(fn, "cancel_match")

    async def timeout_match_on_chain(self, match_id: str) -> str:
        """Timeout a stale locked match (permissionless on-chain)."""
        await self._ensure_initialized()
        fn = self._contract.functions.timeoutMatch(match_id_to_bytes(match_id))
        return await self._send_tx(fn, "timeout_match")

    # ── Read operations ──

    async def get_match_pool(self, match_id: str) -> dict | None:
        """Fetch match pool data from contract. Returns None if not found."""
        await self._ensure_initialized()
        try:
            data = await self._contract.functions.matches(match_id_to_bytes(match_id)).call()
            # Struct returns as tuple: (fighterA, fighterB, status, winner, ...)
            if data[2] == 0:  # MatchStatus.None = not initialized
                return None
            return {
                "fighter_a": data[0],
                "fighter_b": data[1],
                "status": data[2],
                "winner": data[3],
                "side_a_bet_count": data[4],
                "side_b_bet_count": data[5],
                "winning_bet_count": data[6],
                "bet_count": data[7],
                "fee_bps": data[8],
                "side_a_total": data[9],
                "side_b_total": data[10],
                "created_at": data[11],
                "lock_timestamp": data[12],
                "resolve_timestamp": data[13],
                "cancel_timestamp": data[14],
                "min_bet": data[15],
                "betting_window": data[16],
                "fees_withdrawn": data[17],
            }
        except Exception:
            logger.exception("Failed to fetch match pool %s", match_id)
            return None

    async def get_bet(self, match_id: str, bettor_address: str) -> dict | None:
        """Fetch bet info from contract. Returns None if no bet."""
        await self._ensure_initialized()
        try:
            data = await self._contract.functions.bets(
                match_id_to_bytes(match_id),
                self._w3.to_checksum_address(bettor_address),
            ).call()
            if data[0] == 0:  # amount == 0 means no bet
                return None
            return {"amount": data[0], "side": data[1], "claimed": data[2]}
        except Exception:
            logger.exception("Failed to fetch bet for %s on %s", bettor_address, match_id)
            return None

    async def bet_exists(self, match_id: str, bettor_address: str) -> bool | None:
        """Three-state check: True (bet exists), False (no bet), None (RPC error)."""
        await self._ensure_initialized()
        try:
            data = await self._contract.functions.bets(
                match_id_to_bytes(match_id),
                self._w3.to_checksum_address(bettor_address),
            ).call()
            return data[0] > 0  # amount > 0 means bet exists
        except Exception:
            logger.exception("RPC error checking bet existence")
            return None


# Module-level singleton
evm_client = EVMClient()
