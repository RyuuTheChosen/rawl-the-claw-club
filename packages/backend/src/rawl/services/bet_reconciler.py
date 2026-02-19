"""Celery Beat tasks for bet reconciliation and stale match timeout.

reconcile_bets (every 60s):
  - Syncs DB bet status with on-chain contract state for confirmed bets on
    cancelled/resolved matches.
  - Expires pending bets older than 1 hour with no on-chain bet.

timeout_stale_matches (every 60s):
  - Submits timeout_match on-chain for matches locked > 30 minutes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import Ignore

from rawl.celery_app import celery, celery_async_run, get_sync_redis

logger = logging.getLogger(__name__)

RECONCILE_BATCH_SIZE = 50
PENDING_EXPIRY_SECONDS = 3600  # 1 hour
LOCK_TIMEOUT_SECONDS = 1800  # 30 minutes


@celery.task(name="rawl.services.bet_reconciler.reconcile_bets")
def reconcile_bets():
    """Reconcile confirmed bets on finished matches with on-chain state."""
    celery_async_run(_reconcile_bets_async())


@celery.task(name="rawl.services.bet_reconciler.timeout_stale_matches")
def timeout_stale_matches():
    """Timeout matches stuck in locked state beyond the threshold."""
    celery_async_run(_timeout_stale_matches_async())


async def _reconcile_bets_async():
    from sqlalchemy import select

    from rawl.db.models.bet import Bet
    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.evm.client import evm_client

    try:
        # --- Phase 1: Reconcile confirmed bets on finished matches ---
        async with worker_session_factory() as db:
            query = (
                select(Bet, Match)
                .join(Match, Bet.match_id == Match.id)
                .where(
                    Bet.status == "confirmed",
                    Match.status.in_(["cancelled", "resolved"]),
                )
                .limit(RECONCILE_BATCH_SIZE)
            )
            result = await db.execute(query)
            rows = result.all()

        for bet, match in rows:
            try:
                # Check on-chain bet existence
                exists = await evm_client.bet_exists(
                    str(bet.match_id), bet.wallet_address
                )

                if exists is None:
                    # RPC error — skip, don't falsely update
                    logger.warning(
                        "RPC error checking bet, skipping",
                        extra={"bet_id": str(bet.id), "match_id": str(match.id)},
                    )
                    continue

                if exists:
                    # Bet still on-chain — check if claimed flag is set
                    bet_data = await evm_client.get_bet(
                        str(bet.match_id), bet.wallet_address
                    )
                    if bet_data and bet_data.get("claimed"):
                        new_status = "claimed" if match.status == "resolved" else "refunded"
                    else:
                        continue  # Not yet claimed/refunded

                else:
                    # No bet on-chain (shouldn't happen on EVM, but handle gracefully)
                    continue

                old_status = bet.status
                async with worker_session_factory() as db:
                    result = await db.execute(
                        select(Bet).where(Bet.id == bet.id, Bet.status == "confirmed")
                    )
                    b = result.scalar_one_or_none()
                    if b:
                        b.status = new_status
                        if new_status == "claimed":
                            b.claimed_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.info(
                            "Bet reconciled",
                            extra={
                                "bet_id": str(bet.id),
                                "match_id": str(match.id),
                                "old_status": old_status,
                                "new_status": new_status,
                            },
                        )

            except Exception:
                logger.exception(
                    "Error reconciling bet",
                    extra={"bet_id": str(bet.id)},
                )

        # --- Phase 2: Expire stale pending bets ---
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=PENDING_EXPIRY_SECONDS)
        async with worker_session_factory() as db:
            query = (
                select(Bet)
                .where(Bet.status == "pending", Bet.created_at < cutoff)
                .limit(RECONCILE_BATCH_SIZE)
            )
            result = await db.execute(query)
            stale_pending = result.scalars().all()

        for bet in stale_pending:
            try:
                exists = await evm_client.bet_exists(
                    str(bet.match_id), bet.wallet_address
                )

                if exists is None:
                    continue  # RPC error, skip

                if exists:
                    # Bet exists on-chain — promote to confirmed
                    async with worker_session_factory() as db:
                        result = await db.execute(
                            select(Bet).where(Bet.id == bet.id, Bet.status == "pending")
                        )
                        b = result.scalar_one_or_none()
                        if b:
                            b.status = "confirmed"
                            await db.commit()
                            logger.info(
                                "Stale pending bet promoted to confirmed",
                                extra={"bet_id": str(bet.id)},
                            )
                    continue

                # No bet on-chain — expire
                async with worker_session_factory() as db:
                    result = await db.execute(
                        select(Bet).where(Bet.id == bet.id, Bet.status == "pending")
                    )
                    b = result.scalar_one_or_none()
                    if b:
                        b.status = "expired"
                        await db.commit()
                        logger.info(
                            "Stale pending bet expired",
                            extra={"bet_id": str(bet.id)},
                        )

            except Exception:
                logger.exception(
                    "Error processing stale pending bet",
                    extra={"bet_id": str(bet.id)},
                )

    except Exception:
        logger.exception("Bet reconciliation task failed")


async def _timeout_stale_matches_async():
    from sqlalchemy import func, select

    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.evm.client import evm_client

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=LOCK_TIMEOUT_SECONDS)

        async with worker_session_factory() as db:
            # COALESCE handles rows where locked_at was never set (legacy bug)
            lock_time = func.coalesce(Match.locked_at, Match.created_at)
            result = await db.execute(
                select(Match).where(
                    Match.status == "locked",
                    lock_time < cutoff,
                )
            )
            stale_matches = result.scalars().all()

        if not stale_matches:
            return

        for match in stale_matches:
            match_id = str(match.id)
            try:
                sig = await evm_client.timeout_match_on_chain(match_id)
                logger.info(
                    "Match timed out on-chain",
                    extra={"match_id": match_id, "tx_hash": sig},
                )

                # Update DB
                async with worker_session_factory() as db:
                    result = await db.execute(
                        select(Match).where(Match.id == match.id, Match.status == "locked")
                    )
                    m = result.scalar_one_or_none()
                    if m:
                        m.status = "cancelled"
                        m.cancel_reason = "timeout"
                        m.cancelled_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.info(
                            "Match status updated to cancelled (timeout)",
                            extra={"match_id": match_id},
                        )

            except Exception:
                logger.exception(
                    "Error timing out stale match",
                    extra={"match_id": match_id},
                )

    except Exception:
        logger.exception("Timeout stale matches task failed")
