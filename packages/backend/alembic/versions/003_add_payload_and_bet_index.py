"""Add payload column to failed_uploads and composite index on bets

Revision ID: 003
Revises: 002
Create Date: 2026-02-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FailedUpload: add payload column for retry data
    op.add_column(
        "failed_uploads",
        sa.Column("payload", sa.LargeBinary, nullable=True),
    )

    # Bets: composite index for common query (match_id + wallet_address)
    op.create_index(
        "ix_bet_match_wallet",
        "bets",
        ["match_id", "wallet_address"],
    )


def downgrade() -> None:
    op.drop_index("ix_bet_match_wallet", table_name="bets")
    op.drop_column("failed_uploads", "payload")
