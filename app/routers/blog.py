"""Blog: public feed of published posts + individual post pages.

Content is authored HTML (draft → published). Drafts 404 for the public but
are viewable by admins for preview, so a future agent-drafts/human-approves
pipeline can stage posts before they go live.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BlogPost, PostStatus
from ..security import is_admin, session_user
from ..templating import templates

router = APIRouter()


@router.get("/blog")
def blog_index(request: Request, db: Session = Depends(get_db)):
    # Only posts that are published *and* whose publish time has arrived —
    # a future published_at is a scheduled post and stays hidden until then.
    now = datetime.now(timezone.utc)
    posts = (
        db.execute(
            select(BlogPost)
            .where(BlogPost.status == PostStatus.published)
            .where(BlogPost.published_at.isnot(None))
            .where(BlogPost.published_at <= now)
            .order_by(BlogPost.published_at.desc())
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request, "blog_list.html", {"title": "Blog", "posts": posts}
    )


@router.get("/blog/{slug}")
def blog_post(request: Request, slug: str, db: Session = Depends(get_db)):
    post = db.execute(
        select(BlogPost).where(BlogPost.id == slug)
    ).scalar_one_or_none()

    # Public sees live posts only; admins can preview drafts and scheduled ones.
    if post is None or (
        not post.is_publicly_visible and not is_admin(session_user(request))
    ):
        raise HTTPException(status_code=404, detail="Post not found")

    return templates.TemplateResponse(
        request, "blog_post.html", {"title": post.title, "post": post}
    )
