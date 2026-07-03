"""Import seed binge stories from binge_stories.csv.

The CSV is the raw submission export: column 1 is a timestamp we deliberately
drop (stories display anonymously with no date), column 2 is the story text.
Blank rows are skipped. Every imported story lands pre-approved so it shows up
in the public feed immediately. Idempotent: an identical story_text already in
the table is skipped, so re-running never duplicates.

Usage:
    python -m scripts.import_stories
    python -m scripts.import_stories --file some_other.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import BingeStory, StoryStatus

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "binge_stories.csv"


def run(csv_path: Path) -> None:
    if not csv_path.exists():
        raise SystemExit(f"Not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header row
        texts = []
        for row in reader:
            # story text is the 2nd column; tolerate short/blank rows
            text = (row[1].strip() if len(row) > 1 else "")
            if text:
                texts.append(text)

    added = skipped = 0
    with SessionLocal() as db:
        for text in texts:
            exists = db.execute(
                select(BingeStory.id).where(BingeStory.story_text == text)
            ).scalar_one_or_none()
            if exists:
                skipped += 1
                continue
            db.add(
                BingeStory(
                    story_text=text,
                    display_name=None,  # anonymous
                    show_id=None,
                    status=StoryStatus.approved,
                )
            )
            added += 1
        db.commit()

    print(f"Stories: +{added} imported, {skipped} already present "
          f"({len(texts)} non-blank rows in {csv_path.name}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(DEFAULT_CSV), help="CSV path")
    args = parser.parse_args()
    run(Path(args.file))
