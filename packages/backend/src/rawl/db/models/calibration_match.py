from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rawl.db.base import Base


class CalibrationMatch(Base):
    __tablename__ = "calibration_matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fighter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fighters.id"), nullable=False, index=True
    )
    reference_elo: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_fighter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # win, loss, error
    match_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    round_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    elo_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
