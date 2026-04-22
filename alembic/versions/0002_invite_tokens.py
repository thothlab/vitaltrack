"""Add invite_tokens table.

Revision ID: 0002_invite_tokens
Revises: 0001_init
Create Date: 2026-04-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_invite_tokens"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("inviter_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invite_type", sa.String(20), nullable=False),
        sa.Column("used_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invite_token", "invite_tokens", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_token", table_name="invite_tokens")
    op.drop_table("invite_tokens")
