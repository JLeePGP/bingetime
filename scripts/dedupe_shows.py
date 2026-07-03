"""Collapse duplicate shows that share a TMDB id.

Duplicates arise when a video-backed slug (e.g. `demon-slayer`) and a seeded
slug (`demon-slayer-kimetsu-no-yaiba`) resolve to the same TMDB record. Per the
product rule, the keeper is the one that has a creator video; if none (or more
than one) does, the shortest slug wins deterministically. References in
user_shows and binge_stories are repointed to the keeper before the losers are
deleted, so nothing dangles.

Idempotent: with no duplicates left it reports and exits.

Usage:
    python -m scripts.dedupe_shows           # apply
    python -m scripts.dedupe_shows --dry-run  # report only
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import BingeStory, Show, UserShow

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _pick_keeper(shows: list[Show]) -> Show:
    """Video-backed first, then shortest slug for a stable tiebreak."""
    return sorted(shows, key=lambda s: (not s.has_creator_video, len(s.id), s.id))[0]


def run(dry_run: bool) -> None:
    removed = 0
    with SessionLocal() as db:
        dup_ids = db.execute(
            select(Show.tmdb_id)
            .where(Show.tmdb_id.isnot(None))
            .group_by(Show.tmdb_id)
            .having(func.count() > 1)
        ).scalars().all()

        if not dup_ids:
            print("No duplicate tmdb_ids. Nothing to do.")
            return

        for tmdb_id in dup_ids:
            group = db.execute(
                select(Show).where(Show.tmdb_id == tmdb_id)
            ).scalars().all()
            keeper = _pick_keeper(group)
            losers = [s for s in group if s.id != keeper.id]
            print(f"tmdb {tmdb_id}: keep {keeper.id} "
                  f"(vid={keeper.has_creator_video}), drop {[s.id for s in losers]}")
            if dry_run:
                continue

            for loser in losers:
                # Repoint user_shows, skipping rows that would collide with an
                # existing (user, keeper) entry (the unique constraint).
                for us in db.execute(
                    select(UserShow).where(UserShow.show_id == loser.id)
                ).scalars().all():
                    clash = db.execute(
                        select(UserShow).where(
                            UserShow.user_id == us.user_id,
                            UserShow.show_id == keeper.id,
                        )
                    ).scalar_one_or_none()
                    if clash:
                        db.delete(us)
                    else:
                        us.show_id = keeper.id
                # Repoint any stories tagged with the loser.
                for story in db.execute(
                    select(BingeStory).where(BingeStory.show_id == loser.id)
                ).scalars().all():
                    story.show_id = keeper.id

                db.delete(loser)
                removed += 1

        if dry_run:
            print("\n[dry-run] no changes written.")
        else:
            db.commit()
            print(f"\nRemoved {removed} duplicate show(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
