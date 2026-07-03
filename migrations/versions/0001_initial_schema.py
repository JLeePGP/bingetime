"""initial schema — shows, creator_videos, binge_stories, users, user_shows

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# create_type=False: these are created once explicitly in upgrade() below,
# so create_table must not also emit CREATE TYPE for them.
category = postgresql.ENUM("movie", "tv", "anime", name="category", create_type=False)
platform = postgresql.ENUM(
    "tiktok", "youtube", "instagram", name="platform", create_type=False
)
story_status = postgresql.ENUM(
    "pending", "approved", "rejected", name="story_status", create_type=False
)
user_show_status = postgresql.ENUM(
    "watchlist", "in_progress", "completed", name="user_show_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    category.create(bind, checkfirst=True)
    platform.create(bind, checkfirst=True)
    story_status.create(bind, checkfirst=True)
    user_show_status.create(bind, checkfirst=True)

    op.create_table(
        "shows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("tmdb_id", sa.String(), nullable=True),
        sa.Column("category", category, nullable=False),
        sa.Column("seasons", sa.Integer(), nullable=True),
        sa.Column("episodes", sa.Integer(), nullable=True),
        sa.Column("avg_runtime_min", sa.Integer(), nullable=True),
        sa.Column("total_runtime_min", sa.Integer(), nullable=True),
        sa.Column("poster_url", sa.String(), nullable=True),
        sa.Column("streaming_platforms", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("has_creator_video", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shows_title", "shows", ["title"])
    op.create_index("ix_shows_category", "shows", ["category"])

    op.create_table(
        "creator_videos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("show_id", sa.String(), nullable=False),
        sa.Column("video_url", sa.String(), nullable=False),
        sa.Column("platform", platform, nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("thumbnail_url", sa.String(), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_url"),
    )
    op.create_index("ix_creator_videos_show_id", "creator_videos", ["show_id"])

    op.create_table(
        "binge_stories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("show_id", sa.String(), nullable=True),
        sa.Column("story_text", sa.Text(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", story_status, nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_binge_stories_status", "binge_stories", ["status"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_shows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("show_id", sa.String(), nullable=False),
        sa.Column("status", user_show_status, nullable=False),
        sa.Column("times_watched", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planner_hours_per_week", sa.Integer(), nullable=True),
        sa.Column("planner_finish_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_shows_user_id", "user_shows", ["user_id"])
    op.create_index("ix_user_shows_show_id", "user_shows", ["show_id"])
    op.create_index(
        "ix_user_shows_user_show", "user_shows", ["user_id", "show_id"], unique=True
    )


def downgrade() -> None:
    op.drop_table("user_shows")
    op.drop_table("users")
    op.drop_table("binge_stories")
    op.drop_table("creator_videos")
    op.drop_table("shows")

    bind = op.get_bind()
    user_show_status.drop(bind, checkfirst=True)
    story_status.drop(bind, checkfirst=True)
    platform.drop(bind, checkfirst=True)
    category.drop(bind, checkfirst=True)
