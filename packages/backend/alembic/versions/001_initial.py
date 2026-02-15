"""Initial schema - all 7 tables

Revision ID: 001
Revises:
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_address", sa.String(44), unique=True, nullable=False),
        sa.Column("api_key_hash", sa.String(64), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_wallet_address", "users", ["wallet_address"])

    # Fighters
    op.create_table(
        "fighters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("character", sa.String(64), nullable=False),
        sa.Column("model_path", sa.String(512), nullable=False),
        sa.Column("elo_rating", sa.Float, nullable=False, server_default="1200.0"),
        sa.Column("matches_played", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="validating"),
        sa.Column("adapter_version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fighters_owner_id", "fighters", ["owner_id"])
    op.create_index("ix_fighters_game_id", "fighters", ["game_id"])

    # Matches
    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("match_format", sa.Integer, nullable=False, server_default="3"),
        sa.Column("fighter_a_id", UUID(as_uuid=True), sa.ForeignKey("fighters.id"), nullable=False),
        sa.Column("fighter_b_id", UUID(as_uuid=True), sa.ForeignKey("fighters.id"), nullable=False),
        sa.Column("winner_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("match_type", sa.String(20), nullable=False, server_default="ranked"),
        sa.Column("has_pool", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("match_hash", sa.String(64), nullable=True),
        sa.Column("hash_version", sa.Integer, nullable=True),
        sa.Column("adapter_version", sa.String(16), nullable=True),
        sa.Column("round_history", sa.Text, nullable=True),
        sa.Column("replay_s3_key", sa.String(256), nullable=True),
        sa.Column("onchain_match_id", sa.String(64), nullable=True),
        sa.Column("side_a_total", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("side_b_total", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cancel_reason", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_matches_game_id", "matches", ["game_id"])
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_created_at", "matches", ["created_at"])
    op.create_index("ix_matches_onchain_match_id", "matches", ["onchain_match_id"])

    # Training Jobs
    op.create_table(
        "training_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fighter_id", UUID(as_uuid=True), sa.ForeignKey("fighters.id"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("algorithm", sa.String(16), nullable=False, server_default="PPO"),
        sa.Column("total_timesteps", sa.Integer, nullable=False, server_default="1000000"),
        sa.Column("current_timesteps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reward", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("model_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_jobs_fighter_id", "training_jobs", ["fighter_id"])

    # Bets
    op.create_table(
        "bets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", UUID(as_uuid=True), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("wallet_address", sa.String(44), nullable=False),
        sa.Column("side", sa.String(1), nullable=False),
        sa.Column("amount_sol", sa.Float, nullable=False),
        sa.Column("onchain_bet_pda", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bets_match_id", "bets", ["match_id"])
    op.create_index("ix_bets_wallet_address", "bets", ["wallet_address"])

    # Calibration Matches
    op.create_table(
        "calibration_matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fighter_id", UUID(as_uuid=True), sa.ForeignKey("fighters.id"), nullable=False),
        sa.Column("reference_elo", sa.Integer, nullable=False),
        sa.Column("reference_fighter_id", sa.String(64), nullable=False),
        sa.Column("result", sa.String(10), nullable=True),
        sa.Column("match_hash", sa.String(64), nullable=True),
        sa.Column("round_history", sa.Text, nullable=True),
        sa.Column("elo_change", sa.Float, nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_calibration_matches_fighter_id", "calibration_matches", ["fighter_id"])

    # Failed Uploads (dead-letter queue)
    op.create_table(
        "failed_uploads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", UUID(as_uuid=True), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("s3_key", sa.String(256), nullable=False),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="failed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_failed_uploads_match_id", "failed_uploads", ["match_id"])


def downgrade() -> None:
    op.drop_table("failed_uploads")
    op.drop_table("calibration_matches")
    op.drop_table("bets")
    op.drop_table("training_jobs")
    op.drop_table("matches")
    op.drop_table("fighters")
    op.drop_table("users")
