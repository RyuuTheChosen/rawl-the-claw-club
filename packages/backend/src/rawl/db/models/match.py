from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rawl.db.base import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    match_format: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    fighter_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fighters.id"), nullable=False
    )
    fighter_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fighters.id"), nullable=False
    )
    winner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", index=True
    )  # open, locked, resolved, cancelled, pending_resolution, resolution_failed
    match_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ranked"
    )  # ranked, challenge, exhibition
    has_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    match_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    round_history: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    replay_s3_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    onchain_match_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    side_a_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    side_b_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    chain: Mapped[str] = mapped_column(String(10), nullable=False, default="base")
    cancel_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
