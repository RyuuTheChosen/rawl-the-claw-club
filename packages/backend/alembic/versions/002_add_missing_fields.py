"""Add missing fields: bet.claimed_at, fighter.division_tier, training_job.tier/gpu_type/queue_position

Revision ID: 002
Revises: 001
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bet: add claimed_at timestamp
    op.add_column("bets", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))

    # Fighter: add division_tier
    op.add_column(
        "fighters",
        sa.Column("division_tier", sa.String(20), nullable=False, server_default="Bronze"),
    )

    # TrainingJob: add tier, gpu_type, queue_position
    op.add_column(
        "training_jobs",
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
    )
    op.add_column(
        "training_jobs",
        sa.Column("gpu_type", sa.String(16), nullable=True),
    )
    op.add_column(
        "training_jobs",
        sa.Column("queue_position", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("training_jobs", "queue_position")
    op.drop_column("training_jobs", "gpu_type")
    op.drop_column("training_jobs", "tier")
    op.drop_column("fighters", "division_tier")
    op.drop_column("bets", "claimed_at")
