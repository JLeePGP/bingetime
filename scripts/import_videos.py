"""Import videos.csv into creator_videos, creating/matching shows.

Each CSV row's `title` column is already a slug (e.g. one-piece); it becomes
the show id. `category` sets the show category. A humanized title is stored
as a placeholder that TMDB enrichment later overwrites with the canonical one.

Idempotent: shows are get-or-created; a video is skipped if its URL already
exists. Safe to re-run after adding rows to the CSV.

Usage:
    python -m scripts.import_videos [path/to/videos.csv]
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Category, CreatorVideo, Platform, Show
from app.titles import humanize

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "videos.csv"


def parse_views(raw: str) -> int:
    return int((raw or "0").replace(",", "").strip() or 0)


def parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def run(csv_path: Path) -> None:
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}")

    created_shows = updated_shows = new_videos = skipped = 0
    with SessionLocal() as db:
        # Cache shows touched this run: Session.get() won't return pending
        # (unflushed) rows, so a slug repeated across CSV rows would otherwise
        # be created twice.
        seen: dict[str, Show] = {}
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                slug = (row["title"] or "").strip()
                if not slug:
                    continue

                show = seen.get(slug) or db.get(Show, slug)
                if show is None:
                    show = Show(
                        id=slug,
                        title=humanize(slug),
                        category=Category(row["category"].strip()),
                        has_creator_video=True,
                    )
                    db.add(show)
                    created_shows += 1
                elif not show.has_creator_video:
                    show.has_creator_video = True
                    updated_shows += 1
                seen[slug] = show

                url = (row["video_url"] or "").strip()
                exists = db.execute(
                    select(CreatorVideo.id).where(CreatorVideo.video_url == url)
                ).scalar_one_or_none()
                if exists:
                    skipped += 1
                    continue

                db.add(
                    CreatorVideo(
                        show_id=slug,
                        video_url=url,
                        platform=Platform(row["platform"].strip()),
                        view_count=parse_views(row["view_count"]),
                        posted_date=parse_date(row.get("posted_date", "")),
                    )
                )
                new_videos += 1

        db.commit()

    print(
        f"Done. shows +{created_shows} (updated {updated_shows}), "
        f"videos +{new_videos} (skipped {skipped} existing)."
    )


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    run(path)
