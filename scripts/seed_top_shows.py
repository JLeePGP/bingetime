"""Seed the catalog with the top N titles per category, straight from TMDB.

Pulls the most-voted movies, (live-action) TV shows, and anime, then writes each
with full metadata (runtime, poster, overview, rating, year, status) in one pass
— no separate enrich step needed. Idempotent: a slug that already exists is left
untouched, so this never clobbers video-backed shows or hand-curated entries.

Requires TMDB_API_KEY in .env.

Usage:
    python -m scripts.seed_top_shows                 # 50 of each (default)
    python -m scripts.seed_top_shows --per 30        # 30 of each
    python -m scripts.seed_top_shows --only anime     # just one category
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata

# Titles routinely contain non-Latin-1 characters (ū, ō, é…). The Windows
# console defaults to cp1252, so make stdout UTF-8 to keep progress prints
# from crashing a run mid-way.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Category, Show
from app.services.tmdb import TMDBClient, TMDBError

CATEGORIES = ("anime", "tv", "movie")


def slugify(name: str) -> str:
    """'Attack on Titan' -> 'attack-on-titan'. Keeps articles (unlike
    titles.normalize) so slugs read naturally and stay stable."""
    s = unicodedata.normalize("NFKD", (name or "").strip().casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def run(per: int, only: str | None) -> None:
    try:
        client = TMDBClient()
    except TMDBError as exc:
        sys.exit(f"{exc}. Set TMDB_API_KEY in .env and retry.")

    cats = (only,) if only else CATEGORIES
    added = skipped = failed = 0

    with client, SessionLocal() as db:
        for category in cats:
            print(f"\n== {category} (top {per}) ==")
            try:
                ids = client.top_ids(category, limit=per)
            except Exception as exc:
                print(f"  ! could not list {category}: {exc}")
                continue

            media = "movie" if category == "movie" else "tv"
            for tmdb_id, name in ids:
                slug = slugify(name)
                if not slug:
                    continue
                # Skip if the slug exists OR another show already has this TMDB
                # id (e.g. a video-backed entry under a different slug) — avoids
                # creating a duplicate card for the same title.
                if db.get(Show, slug) is not None:
                    skipped += 1
                    continue
                if db.execute(
                    select(Show.id).where(Show.tmdb_id == str(tmdb_id))
                ).scalar_one_or_none():
                    skipped += 1
                    continue
                try:
                    data = client.details(tmdb_id, media)
                except Exception as exc:
                    print(f"  ! {slug}: {exc}")
                    failed += 1
                    continue

                db.add(
                    Show(
                        id=slug,
                        title=data.title or name,
                        tmdb_id=data.tmdb_id,
                        category=Category(category),
                        seasons=data.seasons,
                        episodes=data.episodes,
                        avg_runtime_min=data.avg_runtime_min,
                        total_runtime_min=data.total_runtime_min,
                        poster_url=data.poster_url,
                        overview=data.overview,
                        tmdb_rating=data.tmdb_rating,
                        release_year=data.release_year,
                        status=data.status,
                        has_creator_video=False,
                    )
                )
                # Commit per row so a mid-run failure keeps prior progress.
                db.commit()
                added += 1
                print(f"  + {slug} -> {data.title} ({data.total_runtime_min} min)")
                time.sleep(0.3)  # be polite to the API

    print(f"\nDone. Added {added}, skipped {skipped} existing, {failed} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--per", type=int, default=50, help="titles per category")
    parser.add_argument("--only", choices=CATEGORIES, help="seed one category only")
    args = parser.parse_args()
    run(per=args.per, only=args.only)
