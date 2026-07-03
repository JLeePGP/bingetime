"""Password hashing + session-based current-user resolution (email/password auth).

Sessions are signed cookies (Starlette SessionMiddleware). We keep a small user
dict in the session so nav rendering needs no DB hit; the full User row is
loaded only on routes that mutate account data.
"""
from __future__ import annotations

import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session

from .config import settings
from .models import User

# bcrypt hard-limits the input to 72 bytes; enforce it at the form layer.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LEN = 8


def password_error(password: str) -> str | None:
    """Return a human message if the password is unacceptable, else None."""
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "Password is too long (max 72 bytes)."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def login_session(request: Request, user: User) -> None:
    request.session["user"] = {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or user.email.split("@")[0],
    }


def logout_session(request: Request) -> None:
    request.session.pop("user", None)


def session_user(request: Request) -> dict | None:
    return request.session.get("user")


def is_admin(user: dict | None) -> bool:
    return bool(user) and user.get("email", "").lower() in settings.admin_email_set


def current_user(request: Request, db: Session) -> User | None:
    """Load the full User row for the logged-in session, or None."""
    sess = session_user(request)
    if not sess:
        return None
    return db.get(User, sess["id"])
