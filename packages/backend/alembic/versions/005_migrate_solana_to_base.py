"""Migrate Solana to Base (EVM): rename columns, adjust wallet widths, add chain

Revision ID: 005
Revises: 004
Create Date: 2026-02-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bets: rename amount_sol → amount_eth
    op.alter_column("bets", "amount_sol", new_column_name="amount_eth")

    # Bets: rename onchain_bet_pda → onchain_bet_id, widen from 64 to 128 chars
    op.alter_column(
        "bets", "onchain_bet_pda",
        new_column_name="onchain_bet_id",
        type_=sa.String(128),
        existing_type=sa.String(64),
        existing_nullable=True,
    )

    # Bets: narrow wallet_address from 44 (base58) to 42 (0x hex)
    op.alter_column(
        "bets", "wallet_address",
        type_=sa.String(42),
        existing_type=sa.String(44),
        existing_nullable=False,
    )

    # Users: narrow wallet_address from 44 to 42
    op.alter_column(
        "users", "wallet_address",
        type_=sa.String(42),
        existing_type=sa.String(44),
        existing_nullable=False,
    )

    # Matches: add chain column for future multi-chain support
    op.add_column(
        "matches",
        sa.Column("chain", sa.String(10), nullable=False, server_default="base"),
    )


def downgrade() -> None:
    op.drop_column("matches", "chain")

    op.alter_column(
        "users", "wallet_address",
        type_=sa.String(44),
        existing_type=sa.String(42),
        existing_nullable=False,
    )

    op.alter_column(
        "bets", "wallet_address",
        type_=sa.String(44),
        existing_type=sa.String(42),
        existing_nullable=False,
    )

    op.alter_column(
        "bets", "onchain_bet_id",
        new_column_name="onchain_bet_pda",
        type_=sa.String(64),
        existing_type=sa.String(128),
        existing_nullable=True,
    )

    op.alter_column("bets", "amount_eth", new_column_name="amount_sol")
