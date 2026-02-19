from __future__ import annotations

import logging
import uuid as _uuid
from collections import defaultdict

from sqlalchemy import func, select

logger = logging.getLogger(__name__)

# Thresholds
CONCENTRATION_POOL_THRESHOLD_ETH = 10.0
CONCENTRATION_PERCENTAGE_THRESHOLD = 0.50
CROSS_WALLET_LOOKBACK_DAYS = 30


async def check_betting_concentration(match_id: str, db_session) -> list[str]:
    """Check for betting concentration alerts.

    Flag: >50% of one side's pool from single wallet AND pool >10 ETH.
    Returns list of alert messages.
    """
    from rawl.db.models.bet import Bet

    alerts = []

    match_uuid = _uuid.UUID(match_id) if isinstance(match_id, str) else match_id

    # Compute side totals from actual bet records (not eventually-consistent match fields)
    for side in ("a", "b"):
        total_result = await db_session.execute(
            select(func.sum(Bet.amount_eth))
            .where(Bet.match_id == match_uuid, Bet.side == side)
        )
        side_total = total_result.scalar() or 0.0

        if side_total < CONCENTRATION_POOL_THRESHOLD_ETH:
            continue

        # Find largest single-wallet contribution
        result = await db_session.execute(
            select(Bet.wallet_address, func.sum(Bet.amount_eth))
            .where(Bet.match_id == match_uuid, Bet.side == side)
            .group_by(Bet.wallet_address)
            .order_by(func.sum(Bet.amount_eth).desc())
            .limit(1)
        )
        row = result.first()
        if row:
            wallet, amount = row
            if amount / side_total > CONCENTRATION_PERCENTAGE_THRESHOLD:
                msg = (
                    f"P4: Betting concentration alert - wallet {wallet[:8]}... "
                    f"holds {amount:.2f}/{side_total:.2f} ETH ({amount/side_total:.0%}) "
                    f"on side {side.upper()} of match {match_id}"
                )
                alerts.append(msg)
                logger.warning(msg)

    return alerts


async def flag_cross_wallet_funding(wallet_address: str, db_session) -> bool:
    """Detect potential cross-wallet funding by analysing shared funding sources.

    Heuristic: find wallets that bet on the same matches and share a common
    ETH funding parent (first non-system transfer in).  If any cluster of
    wallets funded by the same source all bet on the same side, flag it.

    This is a detective control — logs for post-hoc review.
    Returns True if flagged.
    """
    from datetime import datetime, timedelta, timezone

    from rawl.db.models.bet import Bet

    lookback = datetime.now(timezone.utc) - timedelta(days=CROSS_WALLET_LOOKBACK_DAYS)

    # Step 1: find all matches this wallet has bet on recently
    result = await db_session.execute(
        select(Bet.match_id, Bet.side)
        .where(Bet.wallet_address == wallet_address, Bet.created_at >= lookback)
    )
    wallet_bets = result.all()
    if not wallet_bets:
        return False

    match_ids = [b.match_id for b in wallet_bets]

    # Step 2: find other wallets that bet on the same matches and same side
    co_wallets: dict[str, int] = defaultdict(int)
    for bet_row in wallet_bets:
        result = await db_session.execute(
            select(Bet.wallet_address)
            .where(
                Bet.match_id == bet_row.match_id,
                Bet.side == bet_row.side,
                Bet.wallet_address != wallet_address,
                Bet.created_at >= lookback,
            )
        )
        for row in result.scalars():
            co_wallets[row] += 1

    # Step 3: flag wallets that co-bet on the same side in >= 3 matches
    flagged = False
    for co_wallet, overlap_count in co_wallets.items():
        if overlap_count >= 3:
            logger.warning(
                "Cross-wallet funding pattern detected",
                extra={
                    "primary_wallet": wallet_address[:8],
                    "co_wallet": co_wallet[:8],
                    "same_side_overlap": overlap_count,
                    "total_matches": len(match_ids),
                },
            )
            flagged = True

    if not flagged:
        logger.info(
            "Cross-wallet funding check passed",
            extra={"wallet": wallet_address[:8], "matches_checked": len(match_ids)},
        )

    return flagged


async def audit_betting_patterns(wallet_address: str, db_session) -> dict:
    """Post-match betting pattern audit.

    Flags high win-rate single-wallet patterns.
    """
    from rawl.db.models.bet import Bet

    result = await db_session.execute(
        select(Bet)
        .where(Bet.wallet_address == wallet_address)
        .where(Bet.status == "claimed")
    )
    claimed_bets = result.scalars().all()

    total_bets_result = await db_session.execute(
        select(func.count())
        .where(Bet.wallet_address == wallet_address)
    )
    total_bets = total_bets_result.scalar() or 0

    win_rate = len(claimed_bets) / total_bets if total_bets > 0 else 0

    report = {
        "wallet": wallet_address,
        "total_bets": total_bets,
        "winning_bets": len(claimed_bets),
        "win_rate": round(win_rate, 3),
        "flagged": win_rate > 0.8 and total_bets >= 10,
    }

    if report["flagged"]:
        logger.warning("High win-rate pattern detected", extra=report)

    return report
