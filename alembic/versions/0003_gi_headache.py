"""Add gi_records and headache_attacks tables.

Revision ID: 0003_gi_headache
Revises: 0002_invite_tokens
Create Date: 2026-04-24

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_gi_headache"
down_revision = "0002_invite_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    headache_location = postgresql.ENUM(
        "left", "right", "bilateral", "whole",
        name="headache_location", create_type=True,
    )
    headache_character = postgresql.ENUM(
        "pulsating", "pressing", "stabbing", "other",
        name="headache_character", create_type=True,
    )
    headache_location.create(op.get_bind(), checkfirst=True)
    headache_character.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "gi_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pain", sa.Integer, nullable=True),
        sa.Column("nausea", sa.Integer, nullable=True),
        sa.Column("heartburn", sa.Integer, nullable=True),
        sa.Column("bloating", sa.Integer, nullable=True),
        sa.Column("stool_bristol", sa.Integer, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gi_user_time", "gi_records", ["user_id", "occurred_at"])

    op.create_table(
        "headache_attacks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intensity", sa.Integer, nullable=False),
        sa.Column("location",
                  postgresql.ENUM("left", "right", "bilateral", "whole",
                                  name="headache_location", create_type=False),
                  nullable=True),
        sa.Column("character",
                  postgresql.ENUM("pulsating", "pressing", "stabbing", "other",
                                  name="headache_character", create_type=False),
                  nullable=True),
        sa.Column("duration_hours", sa.Float, nullable=True),
        sa.Column("nausea", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vomiting", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("photophobia", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("phonophobia", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("aura", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("triggers", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("disability", sa.Integer, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_headache_user_time", "headache_attacks", ["user_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_headache_user_time", table_name="headache_attacks")
    op.drop_table("headache_attacks")
    op.drop_index("ix_gi_user_time", table_name="gi_records")
    op.drop_table("gi_records")

    op.execute("DROP TYPE IF EXISTS headache_character")
    op.execute("DROP TYPE IF EXISTS headache_location")
