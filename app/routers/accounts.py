"""Accounts: signup/login/logout, watchlist + history dashboard, planner
persistence, and the admin-only binge-story moderation queue."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BingeStory, Show, StoryStatus, User, UserShow, UserShowStatus
from ..security import (
    current_user,
    hash_password,
    is_admin,
    login_session,
    logout_session,
    password_error,
    session_user,
    verify_password,
)
from ..services import planner as planner_service
from ..templating import templates

router = APIRouter(prefix="/account")


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


# --- Signup / login / logout ---------------------------------------------


@router.get("/signup")
def signup_page(request: Request):
    if session_user(request):
        return _redirect("/account")
    return templates.TemplateResponse(request, "auth_signup.html", {"title": "Sign up"})


@router.post("/signup")
def signup(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(),
    password: str = Form(),
    display_name: str = Form(default=""),
):
    email = email.strip().lower()
    error = None
    if "@" not in email or "." not in email:
        error = "Enter a valid email address."
    elif (pw_err := password_error(password)):
        error = pw_err
    elif db.execute(select(User.id).where(User.email == email)).scalar_one_or_none():
        error = "An account with that email already exists."

    if error:
        return templates.TemplateResponse(
            request,
            "auth_signup.html",
            {"title": "Sign up", "error": error, "email": email},
            status_code=400,
        )

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name.strip() or None,
    )
    db.add(user)
    db.commit()
    login_session(request, user)
    return _redirect("/account")


@router.get("/login")
def login_page(request: Request, next: str = "/account"):
    if session_user(request):
        return _redirect("/account")
    return templates.TemplateResponse(
        request, "auth_login.html", {"title": "Log in", "next": next}
    )


@router.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(),
    password: str = Form(),
    next: str = Form(default="/account"),
):
    email = email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth_login.html",
            {"title": "Log in", "error": "Wrong email or password.", "email": email,
             "next": next},
            status_code=401,
        )
    login_session(request, user)
    # Only allow local redirects (avoid open-redirect via ?next=).
    target = next if next.startswith("/") else "/account"
    return _redirect(target)


@router.post("/logout")
def logout(request: Request):
    logout_session(request)
    return _redirect("/")


# --- Dashboard: watchlist + history ---------------------------------------


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return _redirect("/account/login")

    rows = db.execute(
        select(UserShow, Show)
        .join(Show, Show.id == UserShow.show_id)
        .where(UserShow.user_id == user.id)
        .order_by(UserShow.added_at.desc())
    ).all()

    upcoming = [(us, s) for us, s in rows if us.status != UserShowStatus.completed]
    past = [(us, s) for us, s in rows if us.status == UserShowStatus.completed]
    # Total time counts finished shows plus ones in progress (Watching) — not
    # Plan-to-watch, which you haven't started.
    counted = {UserShowStatus.completed, UserShowStatus.in_progress}
    total_watched_min = sum(
        (s.computed_runtime_min or 0) * (us.times_watched or 1)
        for us, s in rows
        if us.status in counted
    )

    return templates.TemplateResponse(
        request,
        "account_dashboard.html",
        {
            "title": "Your binges",
            "user": user,
            "upcoming": upcoming,
            "past": past,
            "total_watched_min": total_watched_min,
            "statuses": [s.value for s in UserShowStatus],
        },
    )


def _get_or_create_user_show(db: Session, user: User, slug: str) -> UserShow | None:
    if db.get(Show, slug) is None:
        return None
    us = db.execute(
        select(UserShow).where(
            UserShow.user_id == user.id, UserShow.show_id == slug
        )
    ).scalar_one_or_none()
    if us is None:
        us = UserShow(user_id=user.id, show_id=slug, status=UserShowStatus.watchlist)
        db.add(us)
    return us


@router.post("/shows/{slug}/add")
def add_to_watchlist(request: Request, slug: str, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return _redirect(f"/account/login?next=/shows/{slug}")
    _get_or_create_user_show(db, user, slug)
    db.commit()
    return _redirect(f"/shows/{slug}")


@router.post("/shows/{slug}/status")
def update_status(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    status: str = Form(),
    times_watched: int = Form(default=1),
    redirect_to: str = Form(default="/account"),
):
    user = current_user(request, db)
    if not user:
        return _redirect("/account/login")
    us = _get_or_create_user_show(db, user, slug)
    if us is not None and status in {s.value for s in UserShowStatus}:
        us.status = UserShowStatus(status)
        us.times_watched = max(1, times_watched)
        if us.status == UserShowStatus.completed:
            us.completed_at = us.completed_at or datetime.now(timezone.utc)
        else:
            us.completed_at = None
        db.commit()
    return _redirect(redirect_to if redirect_to.startswith("/") else "/account")


@router.post("/shows/{slug}/remove")
def remove_show(request: Request, slug: str, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return _redirect("/account/login")
    us = db.execute(
        select(UserShow).where(
            UserShow.user_id == user.id, UserShow.show_id == slug
        )
    ).scalar_one_or_none()
    if us:
        db.delete(us)
        db.commit()
    return _redirect("/account")


@router.post("/shows/{slug}/planner")
def save_planner(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    hours_per_week: float = Form(),
    redirect_to: str = Form(default="/account"),
):
    """Persist a planner setting to the user's show (spec: planner inputs on a
    show persist to the account once it's on the watchlist)."""
    user = current_user(request, db)
    if not user:
        return _redirect(f"/account/login?next=/shows/{slug}")
    show = db.get(Show, slug)
    us = _get_or_create_user_show(db, user, slug)
    if us is not None and show is not None:
        plan = planner_service.build_plan(show.computed_runtime_min or 0, hours_per_week)
        us.planner_hours_per_week = int(hours_per_week)
        us.planner_finish_date = plan.finish_date
        db.commit()
    return _redirect(redirect_to if redirect_to.startswith("/") else f"/shows/{slug}")


# --- Moderation queue (admin only) ----------------------------------------


@router.get("/moderation")
def moderation_queue(request: Request, db: Session = Depends(get_db)):
    user = session_user(request)
    if not user:
        return _redirect("/account/login?next=/account/moderation")
    if not is_admin(user):
        return templates.TemplateResponse(
            request, "403.html", {"title": "Forbidden"}, status_code=403
        )
    pending = (
        db.execute(
            select(BingeStory)
            .where(BingeStory.status == StoryStatus.pending)
            .order_by(BingeStory.submitted_at.asc())
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "account_moderation.html",
        {"title": "Moderation", "pending": pending},
    )


@router.post("/moderation/{story_id}")
def moderate_story(
    request: Request,
    story_id: str,
    db: Session = Depends(get_db),
    decision: str = Form(),
):
    user = session_user(request)
    if not is_admin(user):
        return _redirect("/account/login?next=/account/moderation")
    story = db.get(BingeStory, story_id)
    if story and decision in {"approve", "reject"}:
        story.status = (
            StoryStatus.approved if decision == "approve" else StoryStatus.rejected
        )
        db.commit()
    return _redirect("/account/moderation")
