"""blog_posts: cover_focus_y (vertical focal point for the cover crop/pan)

Revision ID: 0006_blog_cover_focus
Revises: 0005_blog_agent_fields
Create Date: 2026-07-05
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_blog_cover_focus"
down_revision: str | None = "0005_blog_agent_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "blog_posts",
        sa.Column(
            "cover_focus_y",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )


def downgrade() -> None:
    op.drop_column("blog_posts", "cover_focus_y")
