"""Shared Jinja2 environment and template filters."""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .config import settings
from .embeds import build_embed
from .security import is_admin, session_user
from .seo import (
    breadcrumb_jsonld,
    organization_jsonld,
    show_jsonld,
    website_jsonld,
)
from .services.calculator import _humanize_duration

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

_asset_hashes: dict[str, str] = {}


def asset_url(path: str) -> str:
    """Cache-busting static URL: 'css/styles.css' -> '/static/css/styles.css?v=<hash>'.

    The query is an 8-char content hash, computed once per process (i.e. per
    deploy). Because the URL changes whenever the file's bytes change, a browser
    or CDN can cache the asset forever yet always fetch a new version after a
    deploy — this is what prevents new HTML from loading a stale stylesheet.
    """
    rel = path.lstrip("/")
    if rel.startswith("static/"):
        rel = rel[len("static/"):]
    if rel not in _asset_hashes:
        try:
            digest = hashlib.md5((STATIC_DIR / rel).read_bytes()).hexdigest()[:8]
        except OSError:
            digest = "0"
        _asset_hashes[rel] = digest
    return f"/static/{rel}?v={_asset_hashes[rel]}"


def _inject_user(request: Request) -> dict:
    """Make the logged-in user (from the session cookie) available to every
    template as `current_user` / `is_admin`, no per-route wiring needed."""
    user = session_user(request)
    return {"current_user": user, "is_admin": is_admin(user)}


def _inject_seo(request: Request) -> dict:
    """Per-request SEO context: the canonical production origin, a canonical
    URL for this page, and whether it should be excluded from the index.

    Canonicals are built from `settings.base_url` (never the request host) and
    keep only meaningful params — the category filter is a real landing page;
    search (`q`) and pagination are dropped to consolidate duplicates.
    """
    base = settings.base_url.rstrip("/")
    path = request.url.path
    canonical = base + path
    category = request.query_params.get("category")
    if path == "/shows" and category:
        canonical = f"{base}/shows?category={category}"
    noindex = (
        path.startswith("/account")
        or path == "/feedback"
        or (path == "/shows" and bool(request.query_params.get("q")))
    )
    return {"base_url": base, "canonical_url": canonical, "robots_noindex": noindex}


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR), context_processors=[_inject_user, _inject_seo]
)
templates.env.globals["build_embed"] = build_embed
templates.env.globals["clarity_project_id"] = settings.clarity_project_id
templates.env.globals["asset"] = asset_url
templates.env.globals["website_jsonld"] = website_jsonld
templates.env.globals["organization_jsonld"] = organization_jsonld
templates.env.globals["breadcrumb_jsonld"] = breadcrumb_jsonld
templates.env.globals["show_jsonld"] = show_jsonld


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
