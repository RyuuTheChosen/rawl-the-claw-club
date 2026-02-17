from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from rawl.api.schemas.bet import BetResponse, RecordBetRequest
from rawl.db.models.bet import Bet
from rawl.db.models.match import Match
from rawl.dependencies import DbSession
from rawl.solana.pda import derive_bet_pda

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bets"])


@router.get("/bets", response_model=list[BetResponse])
async def list_bets(
    db: DbSession,
    wallet: str = Query(..., max_length=44),
    match_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    """Get bets for a wallet, optionally filtered by match or status."""
    query = select(Bet).where(Bet.wallet_address == wallet)
    if match_id:
        query = query.where(Bet.match_id == match_id)
    if status:
        query = query.where(Bet.status == status)
    query = query.order_by(Bet.created_at.desc()).limit(100)

    result = await db.execute(query)
    bets = result.scalars().all()
    return [BetResponse.model_validate(b, from_attributes=True) for b in bets]


@router.post("/matches/{match_id}/bets", response_model=BetResponse, status_code=201)
async def record_bet(
    db: DbSession,
    match_id: uuid.UUID,
    body: RecordBetRequest,
):
    """Record a bet after the on-chain transaction succeeds.

    The frontend places the bet on-chain first, then calls this endpoint
    to create a tracking record in the database.
    """
    # Verify match exists and is open
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status not in ("open",):
        raise HTTPException(status_code=400, detail="Match is not open for betting")

    # Check for duplicate bet (one bet per wallet per match)
    existing = await db.execute(
        select(Bet).where(
            Bet.match_id == match_id,
            Bet.wallet_address == body.wallet_address,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bet already recorded for this wallet")

    # Derive the on-chain PDA for reference
    try:
        from solders.pubkey import Pubkey

        pda, _ = derive_bet_pda(str(match_id), Pubkey.from_string(body.wallet_address))
        bet_pda_str = str(pda)
    except Exception:
        logger.warning(
            "PDA derivation failed for bet",
            extra={"match_id": str(match_id), "wallet": body.wallet_address},
        )
        bet_pda_str = None

    bet = Bet(
        match_id=match_id,
        wallet_address=body.wallet_address,
        side=body.side,
        amount_sol=body.amount_sol,
        onchain_bet_pda=bet_pda_str,
        status="confirmed",
    )
    db.add(bet)
    await db.commit()
    await db.refresh(bet)

    return BetResponse.model_validate(bet, from_attributes=True)
