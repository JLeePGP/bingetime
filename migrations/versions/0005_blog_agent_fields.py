"""blog_posts: content-agent fields (AEO structure, provenance, review flags)

Revision ID: 0005_blog_agent_fields
Revises: 0004_blog_posts
Create Date: 2026-07-05
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_blog_agent_fields"
down_revision: str | None = "0004_blog_posts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("blog_posts", sa.Column("tldr", sa.Text(), nullable=True))
    op.add_column(
        "blog_posts", sa.Column("share_image_url", sa.String(), nullable=True)
    )
    op.add_column("blog_posts", sa.Column("kicker", sa.String(), nullable=True))
    op.add_column(
        "blog_posts", sa.Column("list_items", postgresql.JSONB(), nullable=True)
    )
    op.add_column("blog_posts", sa.Column("faq", postgresql.JSONB(), nullable=True))
    op.add_column(
        "blog_posts",
        sa.Column(
            "source", sa.String(), nullable=False, server_default="manual"
        ),
    )
    op.add_column(
        "blog_posts", sa.Column("review_flags", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "blog_posts", sa.Column("gen_meta", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    for col in (
        "gen_meta",
        "review_flags",
        "source",
        "faq",
        "list_items",
        "kicker",
        "share_image_url",
        "tldr",
    ):
        op.drop_column("blog_posts", col)
