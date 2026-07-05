"""The citable-facts surface for the blog content agent.

Everything the agent is allowed to state as fact comes from here — real
`Show` rows and aggregates we compute. The agent writes prose *around* this
payload and never does its own arithmetic (the data moat). See
docs/blog-content-agent-spec.md §4.2 / §8.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, CreatorVideo, Show
from .calculator import _humanize_duration


def citable_show(show: Show) -> dict:
    """The fields the agent may cite for one show. Runtime is pre-computed."""
    runtime = show.computed_runtime_min
    return {
        "slug": show.id,
        "title": show.title,
        "category": getattr(show.category, "value", show.category),
        "seasons": show.seasons,
        "episodes": show.episodes,
        "avg_runtime_min": show.avg_runtime_min,
        "total_runtime_min": runtime,
        "runtime_human": _humanize_duration(runtime) if runtime else None,
        "release_year": show.release_year,
        "rating": round(show.tmdb_rating, 1) if show.tmdb_rating else None,
        "platforms": show.streaming_platforms or [],
        "status": show.status,
        "has_creator_video": show.has_creator_video,
    }


def citable_shows(db: Session, slugs: list[str]) -> list[dict]:
    """Full citable data for specific shows (drafting a chosen title)."""
    if not slugs:
        return []
    rows = db.execute(select(Show).where(Show.id.in_(slugs))).scalars().all()
    by_slug = {s.id: s for s in rows}
    # Preserve caller's order; silently drop slugs that don't exist.
    return [citable_show(by_slug[s]) for s in slugs if s in by_slug]


def compact_catalog(db: Session) -> list[dict]:
    """A lean row per show for title ideation — enough to ground angles and
    lock real counts, without the full payload."""
    rows = db.execute(select(Show).order_by(Show.title.asc())).scalars().all()
    out = []
    for s in rows:
        rt = s.computed_runtime_min
        out.append(
            {
                "slug": s.id,
                "title": s.title,
                "category": getattr(s.category, "value", s.category),
                "runtime_min": rt,
                "runtime_human": _humanize_duration(rt) if rt else None,
                "episodes": s.episodes,
                "year": s.release_year,
                "rating": round(s.tmdb_rating, 1) if s.tmdb_rating else None,
                "has_video": s.has_creator_video,
            }
        )
    return out


def trending_slugs(db: Session, limit: int = 12) -> list[str]:
    """Demand signal: shows fronted by the highest-viewed creator videos.
    A proxy for what's spiking, until GSC query data feeds ideation."""
    top_view = func.max(CreatorVideo.view_count).label("v")
    rows = db.execute(
        select(CreatorVideo.show_id, top_view)
        .group_by(CreatorVideo.show_id)
        .order_by(top_view.desc())
        .limit(limit)
    ).all()
    return [r[0] for r in rows]


def catalog_aggregates(db: Session) -> dict:
    """Real catalog-wide totals — the raw material for data-study / link-bait
    posts. All numbers computed here so the agent never has to."""
    total = db.execute(select(func.count()).select_from(Show)).scalar_one()

    by_cat: dict[str, int] = {}
    for cat in Category:
        n = db.execute(
            select(func.count()).select_from(Show).where(Show.category == cat)
        ).scalar_one()
        by_cat[cat.value] = n

    sum_rt = (
        db.execute(
            select(func.sum(Show.total_runtime_min)).where(
                Show.total_runtime_min.isnot(None)
            )
        ).scalar()
        or 0
    )
    rated = db.execute(
        select(func.count(), func.avg(Show.total_runtime_min)).where(
            Show.total_runtime_min.isnot(None)
        )
    ).one()
    avg_rt = int(rated[1]) if rated[1] else None

    def _extreme(order) -> dict | None:
        s = db.execute(
            select(Show)
            .where(Show.total_runtime_min.isnot(None))
            .order_by(order)
            .limit(1)
        ).scalar_one_or_none()
        return citable_show(s) if s else None

    return {
        "total_shows": total,
        "by_category": by_cat,
        "catalog_total_runtime_min": sum_rt,
        "catalog_total_runtime_human": _humanize_duration(sum_rt) if sum_rt else None,
        "avg_runtime_min": avg_rt,
        "avg_runtime_human": _humanize_duration(avg_rt) if avg_rt else None,
        "longest": _extreme(Show.total_runtime_min.desc()),
        "shortest": _extreme(Show.total_runtime_min.asc()),
    }


def valid_slugs(db: Session, slugs: list[str]) -> set[str]:
    """Subset of `slugs` that exist in the catalog (link validation)."""
    if not slugs:
        return set()
    rows = db.execute(select(Show.id).where(Show.id.in_(slugs))).scalars().all()
    return set(rows)


def slug_titles(db: Session, slugs: list[str]) -> dict[str, str]:
    """slug -> canonical show title, for rendering structured list items."""
    if not slugs:
        return {}
    rows = db.execute(
        select(Show.id, Show.title).where(Show.id.in_(slugs))
    ).all()
    return {r[0]: r[1] for r in rows}
