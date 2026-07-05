"""Seed one data-driven launch post so the blog ships with real content.

Builds a "finish in a weekend" list straight from the catalog — every number
and link is real (the anti-slop moat), not model-generated prose. Idempotent:
re-running upserts the same slug and refreshes the list. Run with:

    ./.venv/Scripts/python.exe -m scripts.seed_blog
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import BlogPost, PostStatus, Show
from app.services.calculator import _humanize_duration

SLUG = "shows-you-can-finish-in-a-weekend"
WEEKEND_MIN_MIN = 180  # ~3h — enough to feel like a binge
WEEKEND_MAX_MIN = 900  # ~15h — finishable across a weekend


def _build(shows) -> tuple[str, str]:
    items = []
    for s in shows:
        rt = _humanize_duration(s.computed_runtime_min)
        bits = []
        if s.episodes:
            bits.append(f"{s.episodes} episodes")
        if s.seasons:
            bits.append(f"{s.seasons} season{'' if s.seasons == 1 else 's'}")
        meta = " · ".join(bits)
        items.append(
            f'<li><a href="/shows/{s.id}">{s.title}</a> — '
            f'<strong>{rt}</strong>{" · " + meta if meta else ""}</li>'
        )
    lst = "\n".join(items)
    body = (
        "<p>A free weekend is the perfect window for a proper binge — but only "
        "if you pick something you can actually <em>finish</em>. We pulled every "
        "title in the BingeTime catalog that runs under 15 hours of total watch "
        "time: long enough to sink into, short enough to wrap up by Sunday "
        "night.</p>\n"
        "<p>Here they are, ranked by total runtime — the biggest commitments "
        "first, straight from our data.</p>\n"
        f"<h2>{len(shows)} shows you can finish in a weekend</h2>\n"
        f"<ol>\n{lst}\n</ol>\n"
        "<p>Want to see how any of these fit your exact schedule? Open a show and "
        'use the <a href="/planner">Planner</a> to spread it across your weekend, '
        'or run the numbers on the <a href="/calculator">watch-time '
        "calculator</a>.</p>"
    )
    excerpt = (
        f"Got a free weekend? Here are {len(shows)} complete binges you can "
        "actually finish in two days — ranked by total watch time."
    )
    return body, excerpt


def run() -> None:
    db = SessionLocal()
    try:
        shows = (
            db.execute(
                select(Show)
                .where(Show.total_runtime_min.isnot(None))
                .where(Show.total_runtime_min >= WEEKEND_MIN_MIN)
                .where(Show.total_runtime_min <= WEEKEND_MAX_MIN)
                .order_by(Show.total_runtime_min.desc())
                .limit(12)
            )
            .scalars()
            .all()
        )
        if not shows:
            print("No qualifying shows found; nothing seeded.")
            return

        body, excerpt = _build(shows)
        now = datetime.now(timezone.utc)
        post = db.get(BlogPost, SLUG)
        if post is None:
            post = BlogPost(id=SLUG, published_at=now)
            db.add(post)
        post.title = "Shows You Can Finish in a Weekend"
        post.excerpt = excerpt
        post.body_html = body
        post.author = "BingeTime"
        post.status = PostStatus.published
        if post.published_at is None:
            post.published_at = now
        db.commit()
        print(f"Seeded '{SLUG}' with {len(shows)} shows.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
