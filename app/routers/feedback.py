"""User feedback: a public bug/suggestion form saved to the DB.

Submission needs no account. The admin queue to read + resolve submissions
lives in the accounts router (/account/feedback), reusing the admin gate.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Feedback, FeedbackCategory
from ..security import session_user
from ..services import email as email_service
from ..templating import templates

router = APIRouter()

_CATEGORY_VALUES = {c.value for c in FeedbackCategory}


@router.get("/feedback")
def feedback_page(request: Request, submitted: str = ""):
    return templates.TemplateResponse(
        request,
        "feedback.html",
        {
            "title": "Send feedback",
            "categories": [c.value for c in FeedbackCategory],
            "submitted": submitted == "1",
        },
    )


@router.post("/feedback")
def submit_feedback(
    request: Request,
    db: Session = Depends(get_db),
    category: str = Form(),
    message: str = Form(min_length=1, max_length=5000),
    email: str = Form(default=""),
    page_url: str = Form(default=""),
):
    cat = (
        FeedbackCategory(category)
        if category in _CATEGORY_VALUES
        else FeedbackCategory.other
    )
    sess = session_user(request)
    fb = Feedback(
        category=cat,
        message=message.strip(),
        email=(email.strip() or None),
        page_url=(page_url.strip()[:500] or None),
        user_id=(sess["id"] if sess else None),
    )
    db.add(fb)
    db.commit()
    # Best-effort admin ping; never blocks the response on email.
    email_service.send_feedback_notice(cat.value, fb.message, fb.email)
    return RedirectResponse(url="/feedback?submitted=1", status_code=303)
