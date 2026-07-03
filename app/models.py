"""SQLAlchemy models — mirrors Section 4 of the build spec.

Tables: shows, creator_videos, binge_stories, users, user_shows.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# --- Enums (become native Postgres ENUM types) ---------------------------


class Category(str, enum.Enum):
    movie = "movie"
    tv = "tv"
    anime = "anime"


class Platform(str, enum.Enum):
    tiktok = "tiktok"
    youtube = "youtube"
    instagram = "instagram"


class StoryStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class UserShowStatus(str, enum.Enum):
    watchlist = "watchlist"
    in_progress = "in_progress"
    completed = "completed"


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Tables ---------------------------------------------------------------


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # slug, e.g. one-piece
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tmdb_id: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category"), nullable=False, index=True
    )
    seasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Total episodes across all seasons (TMDB's number_of_episodes), not
    # per-season. See computed_runtime_min for the reconciliation note.
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_runtime_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Authoritative total, set on enrichment as episodes * avg_runtime_min.
    total_runtime_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String, nullable=True)
    streaming_platforms: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    has_creator_video: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Descriptive metadata from TMDB (set on enrichment).
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    tmdb_rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0–10
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Raw TMDB status string, e.g. "Ended", "Returning Series", "Released".
    # Rendered via the status_label filter into "Ended" / "Ongoing" / etc.
    status: Mapped[str | None] = mapped_column(String, nullable=True)

    videos: Mapped[list["CreatorVideo"]] = relationship(
        back_populates="show",
        cascade="all, delete-orphan",
        order_by="CreatorVideo.view_count.desc()",
    )

    @property
    def computed_runtime_min(self) -> int | None:
        """Total runtime in minutes.

        Prefers the stored total_runtime_min (set during TMDB enrichment).
        Falls back to episodes * avg_runtime_min for manually-entered rows.
        Note: `episodes` is the *total* across seasons, so seasons is not a
        factor here — this reconciles TMDB's data shape with the Section 4
        formula, which assumed a per-season episode count.
        """
        if self.total_runtime_min is not None:
            return self.total_runtime_min
        if self.episodes and self.avg_runtime_min:
            return self.episodes * self.avg_runtime_min
        return None


class CreatorVideo(Base):
    __tablename__ = "creator_videos"

    # Spec lists no PK; a surrogate id keeps one-show-to-many-videos clean.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    show_id: Mapped[str] = mapped_column(
        ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform"), nullable=False
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    show: Mapped["Show"] = relationship(back_populates="videos")


class BingeStory(Base):
    __tablename__ = "binge_stories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    show_id: Mapped[str | None] = mapped_column(
        ForeignKey("shows.id", ondelete="SET NULL"), nullable=True
    )
    story_text: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[StoryStatus] = mapped_column(
        Enum(StoryStatus, name="story_status"),
        nullable=False,
        default=StoryStatus.pending,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    # Nullable to allow a future magic-link/passwordless path (Section 8).
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserShow(Base):
    __tablename__ = "user_shows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    show_id: Mapped[str] = mapped_column(
        ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[UserShowStatus] = mapped_column(
        Enum(UserShowStatus, name="user_show_status"),
        nullable=False,
        default=UserShowStatus.watchlist,
    )
    times_watched: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planner_hours_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planner_finish_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        # One row per (user, show); enforces watchlist/history uniqueness.
        Index("ix_user_shows_user_show", "user_id", "show_id", unique=True),
    )
