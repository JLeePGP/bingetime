"""Shared Jinja2 environment and template filters."""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .config import settings
from .embeds import build_embed
from .security import is_admin, session_user
from .services.calculator import _humanize_duration

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _inject_user(request: Request) -> dict:
    """Make the logged-in user (from the session cookie) available to every
    template as `current_user` / `is_admin`, no per-route wiring needed."""
    user = session_user(request)
    return {"current_user": user, "is_admin": is_admin(user)}


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[_inject_user])
templates.env.globals["build_embed"] = build_embed
templates.env.globals["clarity_project_id"] = settings.clarity_project_id


def humanize_count(value: int | None) -> str:
    """1234567 -> '1.2M', 12300 -> '12.3K'. For view counts."""
    n = int(value or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(n)


def humanize_runtime(total_min: int | None) -> str:
    """Minutes -> 'Xd Yh Zm', or an em dash when unknown."""
    if not total_min:
        return "—"
    return _humanize_duration(int(total_min))


_CATEGORY_LABELS = {"movie": "Movie", "tv": "TV", "anime": "Anime"}


def category_label(value) -> str:
    """Category enum or its value -> display label ('tv' -> 'TV')."""
    v = getattr(value, "value", value)
    return _CATEGORY_LABELS.get(v, str(v).title())


# TMDB status string -> friendly label. Anything unmapped passes through.
_STATUS_LABELS = {
    "Returning Series": "Ongoing",
    "In Production": "In production",
    "Planned": "Planned",
    "Pilot": "Pilot",
    "Ended": "Ended",
    "Canceled": "Canceled",
    "Cancelled": "Canceled",
    "Released": "Released",
}


def status_label(value: str | None) -> str | None:
    if not value:
        return None
    return _STATUS_LABELS.get(value, value)


# UserShowStatus value -> friendly watch-state label.
_WATCH_STATE_LABELS = {
    "watchlist": "Plan to watch",
    "in_progress": "Watching",
    "completed": "Watched",
}


def watch_state_label(value) -> str:
    v = getattr(value, "value", value)
    return _WATCH_STATE_LABELS.get(v, str(v).replace("_", " ").title())


templates.env.filters["humanize_count"] = humanize_count
templates.env.filters["humanize_runtime"] = humanize_runtime
templates.env.filters["category_label"] = category_label
templates.env.filters["status_label"] = status_label
templates.env.filters["watch_state_label"] = watch_state_label
