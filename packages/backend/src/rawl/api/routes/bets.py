from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import aliased

from rawl.api.schemas.bet import BetResponse, BetWithMatchResponse, RecordBetRequest
from rawl.db.models.bet import Bet
from rawl.db.models.fighter import Fighter
from rawl.db.models.match import Match
from rawl.dependencies import DbSession
from rawl.solana.pda import derive_bet_pda

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bets"])


def _bet_with_match(bet: Bet, match: Match, name_a: str | None, name_b: str | None):
    data = {c.key: getattr(bet, c.key) for c in Bet.__table__.columns}
    data["game_id"] = match.game_id
    data["fighter_a_name"] = name_a
    data["fighter_b_name"] = name_b
    data["match_status"] = match.status
    data["match_winner_id"] = match.winner_id
    return BetWithMatchResponse.model_validate(data)


@router.get("/bets", response_model=list[BetWithMatchResponse])
async def list_bets(
    db: DbSession,
    wallet: str = Query(..., max_length=44),
    match_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    """Get bets for a wallet with match context, optionally filtered by match or status."""
    fa = aliased(Fighter, name="fa")
    fb = aliased(Fighter, name="fb")
    query = (
        select(
            Bet,
            Match,
            fa.name.label("fighter_a_name"),
            fb.name.label("fighter_b_name"),
        )
        .join(Match, Bet.match_id == Match.id)
        .outerjoin(fa, Match.fighter_a_id == fa.id)
        .outerjoin(fb, Match.fighter_b_id == fb.id)
        .where(Bet.wallet_address == wallet)
    )
    if match_id:
        query = query.where(Bet.match_id == match_id)
    if status:
        query = query.where(Bet.status == status)
    query = query.order_by(Bet.created_at.desc()).limit(100)

    result = await db.execute(query)
    rows = result.all()
    return [_bet_with_match(bet, match, na, nb) for bet, match, na, nb in rows]


class SyncBetRequest(BaseModel):
    wallet_address: str = Field(..., max_length=44)

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", v):
            raise ValueError("Invalid wallet address")
        return v


@router.post("/bets/{bet_id}/sync", response_model=BetWithMatchResponse)
async def sync_bet_status(
    db: DbSession,
    bet_id: uuid.UUID,
    body: SyncBetRequest,
):
    """Sync a bet's status by checking on-chain state.

    Verifies the on-chain PDA is gone (claimed/refunded) and updates the DB
    accordingly. Safe because it reads on-chain truth, not frontend input.
    """
    fa = aliased(Fighter, name="fa")
    fb = aliased(Fighter, name="fb")
    query = (
        select(
            Bet,
            Match,
            fa.name.label("fighter_a_name"),
            fb.name.label("fighter_b_name"),
        )
        .join(Match, Bet.match_id == Match.id)
        .outerjoin(fa, Match.fighter_a_id == fa.id)
        .outerjoin(fb, Match.fighter_b_id == fb.id)
        .where(Bet.id == bet_id)
    )
    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Bet not found")

    bet, match, name_a, name_b = row

    # Authorization: wallet must match
    if bet.wallet_address != body.wallet_address:
        raise HTTPException(status_code=403, detail="Wallet mismatch")

    # Only sync bets that are still confirmed
    if bet.status != "confirmed":
        return _bet_with_match(bet, match, name_a, name_b)

    # Check on-chain state
    if not bet.onchain_bet_pda:
        return _bet_with_match(bet, match, name_a, name_b)

    from solders.pubkey import Pubkey

    from rawl.solana.client import solana_client

    pda = Pubkey.from_string(bet.onchain_bet_pda)
    exists = await solana_client.account_exists(pda)

    if exists is None:
        # RPC error — can't determine state, return current
        return _bet_with_match(bet, match, name_a, name_b)

    if exists:
        # PDA still exists — user hasn't claimed/refunded yet
        return _bet_with_match(bet, match, name_a, name_b)

    # PDA is gone — update status based on match state
    if match.status == "cancelled":
        bet.status = "refunded"
    elif match.status == "resolved":
        bet.status = "claimed"
        bet.claimed_at = datetime.now(timezone.utc)
    else:
        # Unexpected: PDA gone but match not cancelled/resolved
        return _bet_with_match(bet, match, name_a, name_b)

    await db.commit()
    await db.refresh(bet)
    return _bet_with_match(bet, match, name_a, name_b)


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
