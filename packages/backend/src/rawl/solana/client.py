from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction
from solders.hash import Hash as Blockhash

from rawl.config import settings
from rawl.monitoring.metrics import solana_tx_total
from rawl.solana.deserialize import (
    BetAccount,
    MatchPoolAccount,
    PlatformConfigAccount,
    deserialize_bet,
    deserialize_match_pool,
    deserialize_platform_config,
)
from rawl.solana.instructions import (
    build_cancel_match_ix,
    build_create_match_ix,
    build_lock_match_ix,
    build_resolve_match_ix,
)
from rawl.solana.pda import (
    derive_bet_pda,
    derive_match_pool_pda,
    derive_platform_config_pda,
)

logger = logging.getLogger(__name__)


class SolanaClient:
    """Async Solana RPC client with transaction submission and account reading."""

    def __init__(self) -> None:
        self._client: AsyncClient | None = None
        self._oracle_keypair: Keypair | None = None

    async def initialize(self) -> None:
        """Initialize the Solana RPC connection and load oracle keypair."""
        self._client = AsyncClient(settings.solana_rpc_url)
        self._oracle_keypair = self._load_keypair(settings.oracle_keypair_path)
        logger.info(
            "Solana client initialized",
            extra={
                "rpc_url": settings.solana_rpc_url,
                "oracle": str(self._oracle_keypair.pubkey()) if self._oracle_keypair else "none",
            },
        )

    @staticmethod
    def _load_keypair(path: str) -> Keypair | None:
        """Load a Solana keypair from a JSON file (array of 64 bytes)."""
        kp_path = Path(path)
        if not kp_path.exists():
            logger.warning("Keypair file not found", extra={"path": path})
            return None
        try:
            with open(kp_path) as f:
                key_data = json.load(f)
            return Keypair.from_bytes(bytes(key_data))
        except Exception:
            logger.exception("Failed to load keypair", extra={"path": path})
            return None

    @property
    def oracle_keypair(self) -> Keypair:
        if not self._oracle_keypair:
            raise RuntimeError("Oracle keypair not loaded")
        return self._oracle_keypair

    @property
    def oracle_pubkey(self) -> Pubkey:
        return self.oracle_keypair.pubkey()

    async def get_health(self) -> bool:
        """Check Solana RPC health."""
        if not self._client:
            return False
        try:
            return await self._client.is_connected()
        except Exception:
            return False

    async def send_and_confirm_tx(
        self,
        tx: Transaction,
        instruction_name: str,
    ) -> str:
        """Send a transaction with retry and backoff. Returns signature string."""
        if not self._client:
            raise RuntimeError("Solana client not initialized")

        backoff = [1, 2, 4]
        last_error: Exception | None = None

        for attempt in range(settings.solana_max_retries):
            try:
                result = await self._client.send_transaction(tx)
                sig = result.value
                sig_str = str(sig)

                # Confirm with timeout
                await self._client.confirm_transaction(
                    sig,
                    commitment=Confirmed,
                    sleep_seconds=1,
                    last_valid_block_height=None,
                )

                solana_tx_total.labels(instruction=instruction_name, status="success").inc()
                logger.info(
                    "Transaction confirmed",
                    extra={"instruction": instruction_name, "signature": sig_str},
                )
                return sig_str

            except Exception as e:
                last_error = e
                solana_tx_total.labels(instruction=instruction_name, status="retry").inc()
                if attempt < len(backoff):
                    await asyncio.sleep(backoff[attempt])
                logger.warning(
                    "Transaction attempt failed",
                    extra={
                        "instruction": instruction_name,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

        solana_tx_total.labels(instruction=instruction_name, status="failed").inc()
        raise RuntimeError(
            f"Transaction {instruction_name} failed after {settings.solana_max_retries} retries: {last_error}"
        )

    async def _build_and_send(self, ix, instruction_name: str) -> str:
        """Get recent blockhash, build Transaction, sign with oracle, send."""
        if not self._client:
            raise RuntimeError("Solana client not initialized")

        resp = await self._client.get_latest_blockhash()
        blockhash = resp.value.blockhash

        tx = Transaction.new_signed_with_payer(
            [ix],
            self.oracle_pubkey,
            [self.oracle_keypair],
            blockhash,
        )
        return await self.send_and_confirm_tx(tx, instruction_name)

    # --- Account getters ---

    async def get_match_pool(self, match_id: str) -> MatchPoolAccount | None:
        """Fetch and deserialize a MatchPool account."""
        pda, _ = derive_match_pool_pda(match_id)
        return await self._get_account(pda, deserialize_match_pool)

    async def get_bet(self, match_id: str, bettor: Pubkey) -> BetAccount | None:
        """Fetch and deserialize a Bet account."""
        pda, _ = derive_bet_pda(match_id, bettor)
        return await self._get_account(pda, deserialize_bet)

    async def get_platform_config(self) -> PlatformConfigAccount | None:
        """Fetch and deserialize the PlatformConfig account."""
        pda, _ = derive_platform_config_pda()
        return await self._get_account(pda, deserialize_platform_config)

    async def _get_account(self, pubkey: Pubkey, deserializer):
        """Generic account fetch + deserialize."""
        if not self._client:
            raise RuntimeError("Solana client not initialized")
        try:
            resp = await self._client.get_account_info(pubkey, commitment=Confirmed)
            if resp.value is None:
                return None
            return deserializer(resp.value.data)
        except Exception:
            logger.exception("Failed to fetch account", extra={"pubkey": str(pubkey)})
            return None

    # --- Match operations ---

    async def create_match_on_chain(
        self, match_id: str, fighter_a: Pubkey, fighter_b: Pubkey
    ) -> str:
        """Create a MatchPool on-chain. Returns tx signature."""
        ix = build_create_match_ix(match_id, fighter_a, fighter_b, self.oracle_pubkey)
        return await self._build_and_send(ix, "create_match")

    async def lock_match_on_chain(self, match_id: str) -> str:
        """Lock a match (oracle-only). Returns tx signature."""
        ix = build_lock_match_ix(match_id, self.oracle_pubkey)
        return await self._build_and_send(ix, "lock_match")

    async def resolve_match_on_chain(
        self, match_id: str, winner: int
    ) -> str:
        """Resolve a match with winner (0=SideA, 1=SideB). Returns tx signature."""
        ix = build_resolve_match_ix(match_id, self.oracle_pubkey, winner)
        return await self._build_and_send(ix, "resolve_match")

    async def cancel_match_on_chain(self, match_id: str) -> str:
        """Cancel a match (authority-only via oracle). Returns tx signature."""
        ix = build_cancel_match_ix(match_id, self.oracle_pubkey)
        return await self._build_and_send(ix, "cancel_match")

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


solana_client = SolanaClient()
