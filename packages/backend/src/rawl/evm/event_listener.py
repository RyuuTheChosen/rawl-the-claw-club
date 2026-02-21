"""Contract event listener — replaces Solana account_listener.

Subscribes to RawlBetting contract events via HTTP polling (with WebSocket
upgrade when available). Handles BetPlaced, MatchLocked, MatchResolved,
MatchCancelled, PayoutClaimed, BetRefunded events.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from web3 import AsyncWeb3, AsyncHTTPProvider

from rawl.config import settings
from rawl.evm.abi import CONTRACT_ABI
from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2  # seconds
RECONNECT_BACKOFF_INITIAL = 1
RECONNECT_BACKOFF_MAX = 30
REDIS_LAST_BLOCK_KEY = "evm:last_block"
ODDS_TTL = 300  # 5 minutes
MAX_BLOCK_RANGE = 2000  # max blocks per eth_getLogs call (public RPC safe)
MAX_CATCHUP_BLOCKS = 10000  # if further behind than this, skip to head


class EventListener:
    """Poll contract events and update DB + Redis."""

    def __init__(self):
        self._running = False
        self._w3: AsyncWeb3 | None = None
        self._contract = None
        self._last_block: int = 0

    async def start(self) -> None:
        """Start the event polling loop. Runs until stop() is called."""
        self._running = True
        self._w3 = AsyncWeb3(AsyncHTTPProvider(settings.base_rpc_url))
        self._contract = self._w3.eth.contract(
            address=self._w3.to_checksum_address(settings.contract_address),
            abi=CONTRACT_ABI,
        )

        # Restore last processed block from Redis
        current_head = await self._w3.eth.get_block_number()
        try:
            stored = await redis_pool.get(REDIS_LAST_BLOCK_KEY)
            if stored:
                stored_block = int(stored)
                gap = current_head - stored_block
                if gap > MAX_CATCHUP_BLOCKS:
                    logger.warning(
                        "Stored block %d is %d blocks behind head %d (> %d) — skipping to head",
                        stored_block, gap, current_head, MAX_CATCHUP_BLOCKS,
                    )
                    self._last_block = current_head
                else:
                    self._last_block = stored_block
                    logger.info("Resuming event listener from block %d (%d behind)", stored_block, gap)
        except Exception:
            pass

        if self._last_block == 0:
            self._last_block = current_head
            logger.info("Starting event listener from current block %d", self._last_block)

        backoff = RECONNECT_BACKOFF_INITIAL
        while self._running:
            try:
                await self._poll_loop()
                backoff = RECONNECT_BACKOFF_INITIAL
            except Exception:
                logger.exception("Event listener error, reconnecting in %ds", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    async def stop(self) -> None:
        """Signal the listener to stop."""
        self._running = False

    async def _poll_loop(self) -> None:
        """Continuously poll for new events."""
        while self._running:
            try:
                current_block = await self._w3.eth.get_block_number()
                if current_block > self._last_block:
                    await self._process_blocks(self._last_block + 1, current_block)
                    self._last_block = current_block
                    # Persist to Redis
                    try:
                        await redis_pool.set(REDIS_LAST_BLOCK_KEY, str(current_block))
                    except Exception:
                        pass
            except Exception:
                logger.exception("Error in poll iteration")
                raise  # Trigger reconnect

            await asyncio.sleep(POLL_INTERVAL)

    async def _process_blocks(self, from_block: int, to_block: int) -> None:
        """Fetch and process logs for a block range, chunked to avoid RPC limits."""
        chunk_start = from_block
        while chunk_start <= to_block:
            chunk_end = min(chunk_start + MAX_BLOCK_RANGE - 1, to_block)
            logs = await self._w3.eth.get_logs(
                {
                    "address": self._w3.to_checksum_address(settings.contract_address),
                    "fromBlock": chunk_start,
                    "toBlock": chunk_end,
                }
            )
            for log in logs:
                try:
                    await self._handle_log(log)
                except Exception:
                    logger.exception("Error handling log in block %d", log.get("blockNumber", 0))
            chunk_start = chunk_end + 1

    async def _handle_log(self, log) -> None:
        """Decode and route a single event log."""
        try:
            events = self._contract.events
            # Try each event type
            for event_cls in [
                events.BetPlaced,
                events.MatchLocked,
                events.MatchResolved,
                events.MatchCancelled,
                events.PayoutClaimed,
                events.BetRefunded,
                events.NoWinnersRefunded,
            ]:
                try:
                    decoded = event_cls().process_log(log)
                    await self._dispatch_event(decoded["event"], decoded["args"])
                    return
                except Exception:
                    continue
        except Exception:
            pass  # Unknown event — ignore

    async def _dispatch_event(self, event_name: str, args) -> None:
        """Route decoded event to handler."""
        match_id_hex = args.get("matchId", b"").hex() if isinstance(args.get("matchId"), bytes) else ""
        # Convert bytes32 match_id back to UUID format for DB lookup
        match_id_uuid = self._bytes32_to_uuid(args.get("matchId", b""))

        handler = {
            "BetPlaced": self._handle_bet_placed,
            "MatchLocked": self._handle_match_locked,
            "MatchResolved": self._handle_match_resolved,
            "MatchCancelled": self._handle_match_cancelled,
            "PayoutClaimed": self._handle_payout_claimed,
            "BetRefunded": self._handle_bet_refunded,
            "NoWinnersRefunded": self._handle_bet_refunded,
        }.get(event_name)

        if handler:
            await handler(args, match_id_uuid)
            logger.info("Processed event %s for match %s", event_name, match_id_uuid or match_id_hex)

    @staticmethod
    def _bytes32_to_uuid(b: bytes) -> str | None:
        """Convert bytes32 back to UUID string (first 16 bytes)."""
        if not b or len(b) < 16:
            return None
        import uuid as _uuid
        try:
            return str(_uuid.UUID(bytes=b[:16]))
        except Exception:
            return None

    async def _handle_bet_placed(self, args, match_id_uuid: str | None) -> None:
        """Create/update Bet row in DB, update match side totals."""
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.bet import Bet
        from rawl.db.models.match import Match
        from rawl.db.session import worker_session_factory

        bettor = args["bettor"]
        side = "a" if args["side"] == 0 else "b"
        amount_wei = args["amount"]
        amount_eth = amount_wei / 1e18

        async with worker_session_factory() as db:
            # Check for existing bet record
            existing = await db.execute(
                select(Bet).where(
                    Bet.match_id == match_id_uuid,
                    Bet.wallet_address == bettor.lower(),
                )
            )
            bet = existing.scalar_one_or_none()

            if bet:
                bet.status = "confirmed"
                bet.amount_eth = amount_eth
            else:
                bet = Bet(
                    match_id=match_id_uuid,
                    wallet_address=bettor.lower(),
                    side=side,
                    amount_eth=amount_eth,
                    onchain_bet_id=f"{match_id_uuid}:{bettor.lower()}",
                    status="confirmed",
                )
                db.add(bet)

            # Update match side totals
            match_result = await db.execute(select(Match).where(Match.id == match_id_uuid))
            match = match_result.scalar_one_or_none()
            if match:
                if side == "a":
                    match.side_a_total = (match.side_a_total or 0) + amount_eth
                else:
                    match.side_b_total = (match.side_b_total or 0) + amount_eth

            await db.commit()

        # Publish odds to Redis
        await self._publish_odds(match_id_uuid)

    async def _handle_match_locked(self, args, match_id_uuid: str | None) -> None:
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.match import Match
        from rawl.db.session import worker_session_factory

        async with worker_session_factory() as db:
            result = await db.execute(select(Match).where(Match.id == match_id_uuid))
            match = result.scalar_one_or_none()
            if match:
                match.status = "locked"
                match.locked_at = datetime.now(timezone.utc)
                await db.commit()

    async def _handle_match_resolved(self, args, match_id_uuid: str | None) -> None:
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.match import Match
        from rawl.db.session import worker_session_factory

        winner_side = args["winner"]  # 0=SideA, 1=SideB

        async with worker_session_factory() as db:
            result = await db.execute(select(Match).where(Match.id == match_id_uuid))
            match = result.scalar_one_or_none()
            if match:
                match.status = "resolved"
                match.resolved_at = datetime.now(timezone.utc)
                # Update side totals from event data
                match.side_a_total = args.get("sideATotal", 0) / 1e18
                match.side_b_total = args.get("sideBTotal", 0) / 1e18
                await db.commit()

    async def _handle_match_cancelled(self, args, match_id_uuid: str | None) -> None:
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.match import Match
        from rawl.db.session import worker_session_factory

        async with worker_session_factory() as db:
            result = await db.execute(select(Match).where(Match.id == match_id_uuid))
            match = result.scalar_one_or_none()
            if match:
                match.status = "cancelled"
                match.cancelled_at = datetime.now(timezone.utc)
                await db.commit()

    async def _handle_payout_claimed(self, args, match_id_uuid: str | None) -> None:
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.bet import Bet
        from rawl.db.session import worker_session_factory

        bettor = args["bettor"]

        async with worker_session_factory() as db:
            result = await db.execute(
                select(Bet).where(
                    Bet.match_id == match_id_uuid,
                    Bet.wallet_address == bettor.lower(),
                )
            )
            bet = result.scalar_one_or_none()
            if bet:
                bet.status = "claimed"
                bet.claimed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _handle_bet_refunded(self, args, match_id_uuid: str | None) -> None:
        if not match_id_uuid:
            return

        from sqlalchemy import select

        from rawl.db.models.bet import Bet
        from rawl.db.session import worker_session_factory

        bettor = args["bettor"]

        async with worker_session_factory() as db:
            result = await db.execute(
                select(Bet).where(
                    Bet.match_id == match_id_uuid,
                    Bet.wallet_address == bettor.lower(),
                )
            )
            bet = result.scalar_one_or_none()
            if bet:
                bet.status = "refunded"
                await db.commit()

    async def _publish_odds(self, match_id_uuid: str) -> None:
        """Publish current odds to Redis for real-time display."""
        from sqlalchemy import select

        from rawl.db.models.match import Match
        from rawl.db.session import worker_session_factory

        try:
            async with worker_session_factory() as db:
                result = await db.execute(select(Match).where(Match.id == match_id_uuid))
                match = result.scalar_one_or_none()
                if match:
                    total = (match.side_a_total or 0) + (match.side_b_total or 0)
                    odds = {
                        "side_a_total": match.side_a_total or 0,
                        "side_b_total": match.side_b_total or 0,
                        "total": total,
                        "odds_a": round(total / match.side_a_total, 2) if match.side_a_total else 0,
                        "odds_b": round(total / match.side_b_total, 2) if match.side_b_total else 0,
                    }
                    match_id_hex = match_id_uuid.replace("-", "")[:32]
                    await redis_pool.set(
                        f"odds:{match_id_hex}",
                        json.dumps(odds),
                        ex=ODDS_TTL,
                    )
        except Exception:
            logger.warning("Failed to publish odds for %s", match_id_uuid)


# Module-level singleton
event_listener = EventListener()
