"""SEO surface: robots.txt, sitemap.xml, and JSON-LD structured-data builders.

The JSON-LD builders return plain dicts; templates render them with the Jinja
`tojson` filter (which HTML-escapes for safe embedding in a <script> tag). URLs
are always built from `settings.base_url` — the canonical production origin — so
preview/localhost hosts never leak into canonical tags or the sitemap.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import BlogPost, Category, PostStatus, Show

router = APIRouter()


def _base() -> str:
    return settings.base_url.rstrip("/")


# --- Structured data (JSON-LD) -------------------------------------------


def website_jsonld(base_url: str) -> dict:
    """WebSite schema with a SearchAction — enables a Google sitelinks
    search box that queries the catalog directly."""
    base = base_url.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "BingeTime",
        "url": base + "/",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": base + "/shows?q={search_term_string}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def organization_jsonld(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "BingeTime",
        "url": base + "/",
        "logo": base + "/static/img/og-default.png",
    }


def breadcrumb_jsonld(items: list[tuple[str, str]]) -> dict:
    """items: ordered (name, url) pairs from root to current page."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }


def show_jsonld(show, url: str) -> dict:
    """Movie/TVSeries schema for a show-detail page."""
    is_movie = getattr(show.category, "value", show.category) == "movie"
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Movie" if is_movie else "TVSeries",
        "name": show.title,
        "url": url,
    }
    if show.poster_url:
        data["image"] = show.poster_url
    if show.overview:
        data["description"] = show.overview
    if show.release_year:
        data["datePublished"] = str(show.release_year)
    if not is_movie:
        if show.seasons:
            data["numberOfSeasons"] = show.seasons
        if show.episodes:
            data["numberOfEpisodes"] = show.episodes
    # aggregateRating is intentionally omitted: we don't store TMDB's vote
    # count, and Google flags AggregateRating that lacks ratingCount/reviewCount.
    return data


def article_jsonld(post, url: str, base_url: str) -> dict:
    """Article schema for a blog post."""
    base = base_url.rstrip("/")
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.title,
        "url": url,
        "author": {"@type": "Organization", "name": post.author or "BingeTime"},
        "publisher": {
            "@type": "Organization",
            "name": "BingeTime",
            "logo": {
                "@type": "ImageObject",
                "url": base + "/static/img/og-default.png",
            },
        },
    }
    if post.excerpt:
        data["description"] = post.excerpt
    if post.cover_image_url:
        data["image"] = post.cover_image_url
    if post.published_at:
        data["datePublished"] = post.published_at.isoformat()
    if post.updated_at:
        data["dateModified"] = post.updated_at.isoformat()
    return data


# --- robots.txt + sitemap.xml --------------------------------------------


@router.get("/robots.txt", include_in_schema=False)
def robots() -> Response:
    base = _base()
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /account/\n"
        "Disallow: /api/\n"
        "Disallow: /planner/export.ics\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)) -> Response:
    base = _base()
    # (loc, changefreq, priority) — static landing pages first.
    entries: list[tuple[str, str, str]] = [
        (f"{base}/", "daily", "1.0"),
        (f"{base}/shows", "daily", "0.9"),
        (f"{base}/calculator", "monthly", "0.6"),
        (f"{base}/planner", "monthly", "0.6"),
        (f"{base}/stories", "weekly", "0.6"),
        (f"{base}/blog", "weekly", "0.7"),
    ]
    # Category landing pages ("anime binge times", etc.).
    for cat in Category:
        entries.append((f"{base}/shows?category={cat.value}", "weekly", "0.7"))
    # Published blog posts.
    published = (
        select(BlogPost.id)
        .where(BlogPost.status == PostStatus.published)
        .order_by(BlogPost.id)
    )
    for slug in db.execute(published).scalars():
        entries.append((f"{base}/blog/{slug}", "monthly", "0.6"))
    # Every show-detail page — the bulk of indexable content.
    for sid in db.execute(select(Show.id).order_by(Show.id)).scalars():
        entries.append((f"{base}/shows/{sid}", "weekly", "0.8"))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, changefreq, priority in entries:
        lines.append(
            f"  <url><loc>{escape(loc)}</loc>"
            f"<changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )
    lines.append("</urlset>")
    return Response("\n".join(lines), media_type="application/xml")
