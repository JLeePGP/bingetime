"""blog_posts table

Revision ID: 0004_blog_posts
Revises: 0003_feedback_and_reset
Create Date: 2026-07-04
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_blog_posts"
down_revision: str | None = "0003_feedback_and_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

post_status = postgresql.ENUM(
    "draft", "published", name="post_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    post_status.create(bind, checkfirst=True)

    op.create_table(
        "blog_posts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("excerpt", sa.String(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("status", post_status, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blog_posts_status", "blog_posts", ["status"])


def downgrade() -> None:
    op.drop_table("blog_posts")
    post_status.drop(op.get_bind(), checkfirst=True)
