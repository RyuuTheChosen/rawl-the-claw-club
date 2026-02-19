from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rawl.db.base import Base


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (
        Index("ix_bet_match_wallet", "match_id", "wallet_address"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False, index=True
    )
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(1), nullable=False)  # "a" or "b"
    amount_eth: Mapped[float] = mapped_column(Float, nullable=False)
    onchain_bet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, confirmed, claimed, refunded, expired
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
