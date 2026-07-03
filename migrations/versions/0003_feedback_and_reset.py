"""feedback + password_reset_tokens tables

Revision ID: 0003_feedback_and_reset
Revises: 0002_show_metadata
Create Date: 2026-07-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_feedback_and_reset"
down_revision: str | None = "0002_show_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

feedback_category = postgresql.ENUM(
    "bug", "suggestion", "other", name="feedback_category", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    feedback_category.create(bind, checkfirst=True)

    op.create_table(
        "feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("category", feedback_category, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("page_url", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_resolved", "feedback", ["resolved"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("feedback")
    feedback_category.drop(op.get_bind(), checkfirst=True)
