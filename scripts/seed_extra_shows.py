"""Seed catalog shows that have no creator video (so they aren't in videos.csv).

These are distinct TMDB titles worth listing on their own. Idempotent: a slug
that already exists is left untouched. Run enrich_tmdb afterwards to fill data.

Usage:
    python -m scripts.seed_extra_shows
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Category, Show
from app.titles import humanize

# (slug, category). Title comes from humanize()/TMDB; slug drives the search.
EXTRA_SHOWS: list[tuple[str, str]] = [
    # FMA (2003) and Brotherhood are separate series, each its own entry.
    ("fullmetal-alchemist-brotherhood", "anime"),
]


def run() -> None:
    added = skipped = 0
    with SessionLocal() as db:
        for slug, category in EXTRA_SHOWS:
            if db.get(Show, slug) is not None:
                skipped += 1
                continue
            db.add(
                Show(
                    id=slug,
                    title=humanize(slug),
                    category=Category(category),
                    has_creator_video=False,
                )
            )
            added += 1
        db.commit()
    print(f"Extra shows: +{added} (skipped {skipped} existing).")


if __name__ == "__main__":
    run()
