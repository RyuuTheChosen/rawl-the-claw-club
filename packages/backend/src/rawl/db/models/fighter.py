from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rawl.db.base import Base


class Fighter(Base):
    __tablename__ = "fighters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    game_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    character: Mapped[str] = mapped_column(String(64), nullable=False)
    model_path: Mapped[str] = mapped_column(String(512), nullable=False)
    elo_rating: Mapped[float] = mapped_column(Float, nullable=False, default=1200.0)
    matches_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="validating"
    )  # validating, calibrating, ready, rejected, suspended
    division_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Bronze"
    )  # Bronze, Silver, Gold, Diamond
    adapter_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship("User", back_populates="fighters")
