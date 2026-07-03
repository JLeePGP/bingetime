"""add descriptive metadata to shows — overview, rating, year, status

Revision ID: 0002_show_metadata
Revises: 0001_initial
Create Date: 2026-07-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_show_metadata"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shows", sa.Column("overview", sa.Text(), nullable=True))
    op.add_column("shows", sa.Column("tmdb_rating", sa.Float(), nullable=True))
    op.add_column("shows", sa.Column("release_year", sa.Integer(), nullable=True))
    op.add_column("shows", sa.Column("status", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("shows", "status")
    op.drop_column("shows", "release_year")
    op.drop_column("shows", "tmdb_rating")
    op.drop_column("shows", "overview")
