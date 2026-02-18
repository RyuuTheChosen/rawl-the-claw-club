from __future__ import annotations

import asyncio
import base64
import json
import logging

from rawl.config import settings

logger = logging.getLogger(__name__)

# Reconnection backoff
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0
HEALTH_ALERT_THRESHOLD = 60  # seconds


class AccountListener:
    """On-chain event detection via Solana WebSocket subscription.

    Dedicated service (Kubernetes Deployment, single replica).
    Subscribes to programSubscribe filtered by program ID.
    On MatchPool/Bet PDA update: decode account data, update PostgreSQL,
    publish to Redis live odds cache.
    """

    def __init__(self) -> None:
        self._running = False
        self._ws = None
        self._backoff = INITIAL_BACKOFF
        self._last_slot = 0

    async def start(self) -> None:
        """Start listening for on-chain events."""
        self._running = True
        logger.info("Account listener starting", extra={"ws_url": settings.solana_ws_url})

        while self._running:
            try:
                await self._connect_and_listen()
            except Exception:
                logger.exception("Account listener disconnected")
                if self._running:
                    logger.info(
                        "Reconnecting",
                        extra={"backoff_seconds": self._backoff},
                    )
                    await asyncio.sleep(self._backoff)
                    self._backoff = min(self._backoff * 2, MAX_BACKOFF)

    async def _connect_and_listen(self) -> None:
        """Connect to Solana WebSocket and process account updates."""
        import websockets

        async with websockets.connect(settings.solana_ws_url) as ws:
            self._ws = ws
            self._backoff = INITIAL_BACKOFF  # Reset on successful connect

            # Subscribe to program account changes
            subscribe_msg = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "programSubscribe",
                "params": [
                    settings.program_id,
                    {
                        "encoding": "base64",
                        "commitment": "confirmed",
                    },
                ],
            })
            await ws.send(subscribe_msg)

            # Wait for subscription confirmation
            confirm = json.loads(await ws.recv())
            logger.info("WebSocket subscribed", extra={"subscription_id": confirm.get("result")})

            # Catch-up: reconcile missed events on reconnect
            await self._catch_up()

            async for message in ws:
                if not self._running:
                    break
                try:
                    await self._handle_message(json.loads(message))
                except Exception:
                    logger.exception("Error handling account update")

    async def _handle_message(self, message: dict) -> None:
        """Process an account update notification.

        Discriminator-checks the data to determine if MatchPool or Bet,
        then updates the corresponding PostgreSQL record.
        """
        from rawl.solana.deserialize import (
            MATCH_POOL_DISC,
            BET_DISC,
            MatchStatus,
            deserialize_match_pool,
            deserialize_bet,
        )

        params = message.get("params")
        if not params:
            return

        result = params.get("result")
        if not result:
            return

        value = result.get("value", {})
        account_data = value.get("account", {}).get("data", [])
        if not account_data or len(account_data) < 1:
            return

        # Decode base64 data
        try:
            raw_data = base64.b64decode(account_data[0])
        except Exception:
            return

        if len(raw_data) < 8:
            return

        disc = raw_data[:8]
        slot = result.get("context", {}).get("slot", 0)
        self._last_slot = max(self._last_slot, slot)

        if disc == MATCH_POOL_DISC:
            await self._handle_match_pool_update(raw_data)
        elif disc == BET_DISC:
            await self._handle_bet_update(raw_data)

    async def _handle_match_pool_update(self, data: bytes) -> None:
        """Update PostgreSQL match record from on-chain MatchPool state."""
        from datetime import UTC, datetime

        from sqlalchemy import select

        from rawl.db.models.match import Match
        from rawl.db.session import async_session_factory
        from rawl.solana.deserialize import MatchStatus, deserialize_match_pool

        pool = deserialize_match_pool(data)
        match_id_hex = pool.match_id[:16].hex()

        # Map on-chain status to DB status
        status_map = {
            MatchStatus.OPEN: "open",
            MatchStatus.LOCKED: "locked",
            MatchStatus.RESOLVED: "resolved",
            MatchStatus.CANCELLED: "cancelled",
        }
        db_status = status_map.get(pool.status, "open")

        async with async_session_factory() as db:
            # Find match by onchain_match_id or match_id bytes
            result = await db.execute(
                select(Match).where(Match.onchain_match_id == match_id_hex)
            )
            match = result.scalar_one_or_none()
            if not match:
                return

            match.status = db_status
            match.side_a_total = pool.side_a_total / 1e9  # lamports to SOL
            match.side_b_total = pool.side_b_total / 1e9

            # Record transition timestamps
            if db_status == "locked" and match.locked_at is None:
                match.locked_at = datetime.now(UTC)
            elif db_status == "cancelled" and match.cancelled_at is None:
                match.cancelled_at = datetime.now(UTC)

            await db.commit()

        # Publish updated odds to Redis
        from rawl.redis_client import redis_pool
        total = pool.side_a_total + pool.side_b_total
        if total > 0:
            odds_data = json.dumps({
                "match_id": match_id_hex,
                "side_a_total": pool.side_a_total / 1e9,
                "side_b_total": pool.side_b_total / 1e9,
                "odds_a": total / pool.side_a_total if pool.side_a_total > 0 else 0,
                "odds_b": total / pool.side_b_total if pool.side_b_total > 0 else 0,
            })
            await redis_pool.client.set(f"odds:{match_id_hex}", odds_data, ex=300)

        logger.info(
            "MatchPool updated",
            extra={"match_id": match_id_hex, "status": db_status},
        )

    async def _handle_bet_update(self, data: bytes) -> None:
        """Update or create PostgreSQL bet record from on-chain Bet state."""
        from rawl.solana.deserialize import deserialize_bet, BetSide
        from rawl.db.session import async_session_factory
        from rawl.db.models.bet import Bet
        from rawl.db.models.match import Match
        from sqlalchemy import select
        from datetime import datetime, timezone

        bet_account = deserialize_bet(data)
        bettor_str = str(bet_account.bettor)
        match_id_hex = bet_account.match_id[:16].hex()

        async with async_session_factory() as db:
            # Try to find existing bet by wallet + match
            match_result = await db.execute(
                select(Match).where(Match.onchain_match_id == match_id_hex)
            )
            match = match_result.scalar_one_or_none()
            if not match:
                return

            result = await db.execute(
                select(Bet).where(
                    Bet.match_id == match.id,
                    Bet.wallet_address == bettor_str,
                )
            )
            bet = result.scalar_one_or_none()

            if not bet:
                # Create a new bet record from on-chain data
                side = "a" if bet_account.side == BetSide.SIDE_A else "b"
                bet = Bet(
                    match_id=match.id,
                    wallet_address=bettor_str,
                    side=side,
                    amount_sol=bet_account.amount / 1e9,
                    status="claimed" if bet_account.claimed else "confirmed",
                    claimed_at=datetime.now(timezone.utc) if bet_account.claimed else None,
                )
                db.add(bet)
                await db.commit()
                logger.info(
                    "Bet record created from on-chain data",
                    extra={"match_id": str(match.id), "bettor": bettor_str},
                )
                return

            if bet_account.claimed and bet.status != "claimed":
                bet.status = "claimed"
                bet.claimed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _catch_up(self) -> None:
        """Catch-up on missed events using getProgramAccounts.

        Called on every reconnect for slot-based gap reconciliation.
        """
        from solana.rpc.async_api import AsyncClient
        from solana.rpc.commitment import Confirmed
        from rawl.solana.deserialize import MATCH_POOL_DISC

        try:
            from solders.pubkey import Pubkey

            async with AsyncClient(settings.solana_rpc_url) as client:
                resp = await client.get_program_accounts(
                    pubkey=Pubkey.from_string(settings.program_id),
                    commitment=Confirmed,
                    encoding="base64",
                )
                if resp.value:
                    for account_info in resp.value:
                        data = account_info.account.data
                        if len(data) >= 8 and data[:8] == MATCH_POOL_DISC:
                            await self._handle_match_pool_update(data)

            logger.info("Catch-up reconciliation complete")
        except Exception:
            logger.exception("Catch-up reconciliation failed")

    async def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Account listener stopped")


account_listener = AccountListener()
