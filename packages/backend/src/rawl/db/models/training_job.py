from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rawl.db.base import Base


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fighter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fighters.id"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued, running, completed, failed, cancelled
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free"
    )  # free, standard, pro
    gpu_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # T4, A10G
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    algorithm: Mapped[str] = mapped_column(String(16), nullable=False, default="PPO")
    total_timesteps: Mapped[int] = mapped_column(Integer, nullable=False, default=1_000_000)
    current_timesteps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
