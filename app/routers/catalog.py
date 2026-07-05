"""Catalog: homepage, show grid (search + filter + pagination), show detail."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    BingeStory,
    Category,
    CreatorVideo,
    Show,
    StoryStatus,
    UserShow,
    UserShowStatus,
)
from ..security import current_user
from ..templating import templates

router = APIRouter()

PAGE_SIZE = 24


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    """Hero + featured shows + a carousel of community binge stories."""
    # One clean row of 6, drawn from the most-popular breakdowns (by top video
    # view count) and randomly rotated so the homepage cycles on each visit.
    pool = (
        db.execute(
            select(Show)
            .join(CreatorVideo, CreatorVideo.show_id == Show.id)
            .where(Show.has_creator_video.is_(True))
            .group_by(Show.id)
            .order_by(func.max(CreatorVideo.view_count).desc().nullslast())
            .limit(18)
        )
        .scalars()
        .all()
    )
    featured = random.sample(pool, min(6, len(pool)))
    # Randomize the carousel order so no single story (or its tone) always
    # leads the homepage.
    stories = (
        db.execute(
            select(BingeStory)
            .where(BingeStory.status == StoryStatus.approved)
            .order_by(func.random())
            .limit(12)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "title": "How long to binge any show?",
            "featured": featured,
            "stories": stories,
        },
    )


@router.get("/shows")
def catalog(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="title search"),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    """Paginated, searchable, filterable show grid."""
    stmt = select(Show)
    count_stmt = select(func.count()).select_from(Show)

    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Show.title.ilike(pattern))
        count_stmt = count_stmt.where(Show.title.ilike(pattern))

    valid_category = category if category in {c.value for c in Category} else None
    if valid_category:
        stmt = stmt.where(Show.category == valid_category)
        count_stmt = count_stmt.where(Show.category == valid_category)

    total = db.execute(count_stmt).scalar_one()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    shows = (
        db.execute(
            stmt.order_by(Show.title.asc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "title": "Show catalog",
            "shows": shows,
            "q": q or "",
            "category": valid_category or "",
            "categories": [c.value for c in Category],
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/shows/{slug}")
def show_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    show = db.execute(
        select(Show).where(Show.id == slug).options(selectinload(Show.videos))
    ).scalar_one_or_none()
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")

    # If logged in, surface the user's current state for this show so the page
    # can show the right controls (add vs. update).
    user = current_user(request, db)
    user_show = None
    if user:
        user_show = db.execute(
            select(UserShow).where(
                UserShow.user_id == user.id, UserShow.show_id == slug
            )
        ).scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "show_detail.html",
        {
            "title": show.title,
            "show": show,
            "user_show": user_show,
            "watch_statuses": [s.value for s in UserShowStatus],
        },
    )
