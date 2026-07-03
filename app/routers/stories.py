"""Binge stories: public approved feed + moderated submission.

Submission needs no account (spec Section 5). Approval/moderation is part
of the accounts phase and is intentionally not built here yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BingeStory, Show, StoryStatus
from ..templating import templates

router = APIRouter()


@router.get("/stories")
def stories_feed(request: Request, db: Session = Depends(get_db)):
    stories = (
        db.execute(
            select(BingeStory)
            .where(BingeStory.status == StoryStatus.approved)
            .order_by(BingeStory.submitted_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    shows = db.execute(select(Show).order_by(Show.title)).scalars().all()
    submitted = request.query_params.get("submitted") == "1"
    return templates.TemplateResponse(
        request,
        "stories.html",
        {
            "title": "Binge stories",
            "stories": stories,
            "shows": shows,
            "submitted": submitted,
        },
    )


@router.post("/stories")
def submit_story(
    db: Session = Depends(get_db),
    story_text: str = Form(min_length=1, max_length=5000),
    show_id: str | None = Form(default=None),
    display_name: str | None = Form(default=None),
):
    """Create a pending story for John to approve before it goes public."""
    show_ref = show_id or None
    if show_ref:
        exists = db.execute(
            select(Show.id).where(Show.id == show_ref)
        ).scalar_one_or_none()
        if not exists:
            show_ref = None

    db.add(
        BingeStory(
            show_id=show_ref,
            story_text=story_text.strip(),
            display_name=(display_name or "").strip() or None,
            status=StoryStatus.pending,
        )
    )
    db.commit()
    return RedirectResponse(url="/stories?submitted=1", status_code=303)
