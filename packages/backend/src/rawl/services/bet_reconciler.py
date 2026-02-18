"""Celery Beat tasks for bet reconciliation and stale match timeout.

reconcile_bets (every 60s):
  - Syncs DB bet status with on-chain PDA state for confirmed bets on
    cancelled/resolved matches.
  - Expires pending bets older than 1 hour with no on-chain PDA.

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
    from solders.pubkey import Pubkey
    from sqlalchemy import select

    from rawl.db.models.bet import Bet
    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.solana.client import solana_client

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
                if not bet.onchain_bet_pda:
                    continue

                pda = Pubkey.from_string(bet.onchain_bet_pda)
                exists = await solana_client.account_exists(pda)

                if exists is None:
                    # RPC error — skip, don't falsely update
                    logger.warning(
                        "RPC error checking bet PDA, skipping",
                        extra={"bet_id": str(bet.id), "match_id": str(match.id)},
                    )
                    continue

                if exists:
                    # PDA still exists — user hasn't claimed/refunded yet
                    continue

                # PDA gone — determine new status
                old_status = bet.status
                if match.status == "cancelled":
                    new_status = "refunded"
                else:
                    new_status = "claimed"

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
                if bet.onchain_bet_pda:
                    pda = Pubkey.from_string(bet.onchain_bet_pda)
                    exists = await solana_client.account_exists(pda)

                    if exists is None:
                        continue  # RPC error, skip

                    if exists:
                        # PDA exists — promote to confirmed
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

                # No PDA or PDA doesn't exist — expire
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
    from sqlalchemy import select

    from rawl.db.models.match import Match
    from rawl.db.session import worker_session_factory
    from rawl.solana.client import solana_client
    from rawl.solana.instructions import build_timeout_match_ix

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=LOCK_TIMEOUT_SECONDS)

        async with worker_session_factory() as db:
            result = await db.execute(
                select(Match).where(
                    Match.status == "locked",
                    Match.locked_at < cutoff,
                )
            )
            stale_matches = result.scalars().all()

        if not stale_matches:
            return

        for match in stale_matches:
            match_id = str(match.id)
            try:
                # Submit timeout_match on-chain (permissionless — oracle can call)
                ix = build_timeout_match_ix(match_id, solana_client.oracle_pubkey)
                sig = await solana_client._build_and_send(ix, "timeout_match")
                logger.info(
                    "Match timed out on-chain",
                    extra={"match_id": match_id, "signature": sig},
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
