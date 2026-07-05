"""Blog: public feed of published posts + individual post pages.

Content is authored HTML (draft → published). Drafts 404 for the public but
are viewable by admins for preview, so a future agent-drafts/human-approves
pipeline can stage posts before they go live.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BlogPost, PostStatus
from ..security import current_user, is_admin
from ..templating import templates

router = APIRouter()


@router.get("/blog")
def blog_index(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.execute(
            select(BlogPost)
            .where(BlogPost.status == PostStatus.published)
            .order_by(BlogPost.published_at.desc().nullslast())
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

    # Public sees published only; admins can preview drafts.
    if post is None or (
        post.status != PostStatus.published
        and not is_admin(current_user(request, db))
    ):
        raise HTTPException(status_code=404, detail="Post not found")

    return templates.TemplateResponse(
        request, "blog_post.html", {"title": post.title, "post": post}
    )
