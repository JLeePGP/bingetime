"""Enrich shows with TMDB data (seasons/episodes/runtime/poster/canonical title).

Matches by the show's current title, mapping anime -> TMDB tv. Writes a review
report (tmdb_review.csv) so mismatched auto-picks can be eyeballed and fixed.
Ambiguous titles (e.g. the-flash, one-piece) are the ones to check there.

Requires TMDB_API_KEY in .env. Safe to re-run; --only refreshes one show.

Usage:
    python -m scripts.enrich_tmdb                # all shows missing data
    python -m scripts.enrich_tmdb --all          # re-enrich every show
    python -m scripts.enrich_tmdb --only one-piece
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

# Keep accented/macron titles from crashing progress prints on cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Show
from app.services.tmdb import TMDBClient, TMDBError
from app.titles import search_title as title_for

REPORT = Path(__file__).resolve().parent.parent / "tmdb_review.csv"


def run(refresh_all: bool, only: str | None, missing_meta: bool = False) -> None:
    try:
        client = TMDBClient()
    except TMDBError as exc:
        sys.exit(f"{exc}. Set TMDB_API_KEY in .env and retry.")

    rows_for_review: list[dict] = []
    matched = missed = 0

    with client, SessionLocal() as db:
        stmt = select(Show).order_by(Show.title)
        if only:
            stmt = stmt.where(Show.id == only)
        elif missing_meta:
            # Backfill only shows still lacking a description — i.e. rows that
            # predate the metadata columns. Freshly-seeded shows already have
            # an overview, so they're excluded and won't be re-searched.
            stmt = stmt.where(Show.overview.is_(None))
        elif not refresh_all:
            stmt = stmt.where(Show.total_runtime_min.is_(None))
        shows = db.execute(stmt).scalars().all()

        if not shows:
            print("Nothing to enrich.")
            return

        for show in shows:
            # Search by the stable slug-derived title, not show.title (which
            # enrichment overwrites) so re-runs stay idempotent.
            search_title = title_for(show.id)
            try:
                data = client.fetch_by_title(search_title, show.category.value)
            except Exception as exc:  # keep going; log the failure
                print(f"  ! {show.id}: {exc}")
                missed += 1
                continue

            if not data:
                print(f"  - {show.id}: no TMDB match for '{search_title}'")
                missed += 1
                rows_for_review.append(
                    {"slug": show.id, "searched": search_title, "matched": "", "tmdb_id": ""}
                )
                continue

            rows_for_review.append(
                {
                    "slug": show.id,
                    "searched": search_title,
                    "matched": data.title,
                    "tmdb_id": data.tmdb_id,
                }
            )
            show.tmdb_id = data.tmdb_id
            show.title = data.title or show.title
            show.seasons = data.seasons
            show.episodes = data.episodes
            show.avg_runtime_min = data.avg_runtime_min
            show.total_runtime_min = data.total_runtime_min
            show.overview = data.overview
            show.tmdb_rating = data.tmdb_rating
            show.release_year = data.release_year
            show.status = data.status
            if data.poster_url:
                show.poster_url = data.poster_url
            matched += 1
            print(f"  + {show.id} -> {data.title} ({data.total_runtime_min} min)")
            time.sleep(0.3)  # be polite to the API

        db.commit()

    with REPORT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["slug", "searched", "matched", "tmdb_id"])
        writer.writeheader()
        writer.writerows(rows_for_review)

    print(f"\nMatched {matched}, missed {missed}. Review picks in {REPORT.name}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="re-enrich every show")
    parser.add_argument("--only", help="enrich a single show slug")
    parser.add_argument(
        "--missing-meta",
        action="store_true",
        help="backfill only shows with no description (predate metadata columns)",
    )
    args = parser.parse_args()
    run(refresh_all=args.all, only=args.only, missing_meta=args.missing_meta)
