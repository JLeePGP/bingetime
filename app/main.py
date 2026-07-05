"""BingeTime.tv — FastAPI application entrypoint."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import seo
from .config import settings
from .routers import accounts, calculator, catalog, feedback, planner, stories
from .templating import templates

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=not settings.debug,
    same_site="lax",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(catalog.router)
app.include_router(calculator.router)
app.include_router(planner.router)
app.include_router(stories.router)
app.include_router(feedback.router)
app.include_router(accounts.router)
app.include_router(seo.router)


@app.middleware("http")
async def public_cache_headers(request: Request, call_next):
    """Let a CDN/browser cache public GET responses; never cache the app layer.

    Static assets carry a content-hash query (see `asset_url`), so they can be
    cached long and immutable — a changed file always has a new URL. HTML pages
    get a short cache so a deploy's new markup (and its new asset URLs) reaches
    users in minutes instead of hours. Anything under /account and all non-GET
    requests are always private.
    """
    response = await call_next(request)
    if request.method != "GET" or response.status_code != 200:
        return response
    if request.url.path.startswith("/static/"):
        response.headers.setdefault(
            "Cache-Control", "public, max-age=31536000, immutable"
        )
    elif not request.url.path.startswith(("/account", "/api/")):
        response.headers.setdefault(
            "Cache-Control", f"public, max-age={settings.page_cache_seconds}"
        )
    return response


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(404)
async def not_found(request: Request, exc) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "404.html", {"title": "Not found"}, status_code=404
    )
