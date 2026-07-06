"""Admin blog CMS + content-agent panel: browse / create / edit / schedule /
publish / delete BlogPosts, and generate agent-drafted posts (title ideation →
pick/type → draft → review).

Lives under /account/blog so it inherits the private-cache + noindex treatment
every /account path gets. Access is gated by the same is_admin session check as
the story/feedback moderation queues.

Publishing/scheduling is expressed purely via `published_at` (see
BlogPost.is_publicly_visible). Agent generation lives in services/blog_agent.py;
this router just orchestrates it and persists drafts.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import BlogPost, PostStatus, Show
from ..security import is_admin, session_user
from ..services import blog_agent, blog_lint, covers
from ..templating import templates

router = APIRouter(prefix="/account/blog")

_STATUS_VALUES = [s.value for s in PostStatus]
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _admin_guard(request: Request):
    user = session_user(request)
    if not user:
        return _redirect("/account/login?next=/account/blog")
    if not is_admin(user):
        return templates.TemplateResponse(
            request, "403.html", {"title": "Forbidden"}, status_code=403
        )
    return None


def slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")


def _unique_slug(db: Session, base: str) -> str:
    base = base or "post"
    slug, n = base, 2
    while db.get(BlogPost, slug) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _parse_publish_at(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _apply_status(post: BlogPost, status_value: str, publish_at: datetime | None) -> None:
    if status_value == PostStatus.published.value:
        post.status = PostStatus.published
        if publish_at is not None:
            post.published_at = publish_at
        elif post.published_at is None:
            post.published_at = datetime.now(timezone.utc)
    else:
        post.status = PostStatus.draft


def _parse_json_field(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        val = json.loads(raw)
        return val or None
    except json.JSONDecodeError:
        return None


# --- Cover rendering ------------------------------------------------------


def _poster_urls(db: Session, cover_slug: str | None, cited: list[str]) -> list[str]:
    order: list[str] = []
    if cover_slug:
        order.append(cover_slug)
    for s in cited or []:
        if s not in order:
            order.append(s)
    order = order[:3]
    if not order:
        return []
    rows = db.execute(
        select(Show.id, Show.poster_url).where(Show.id.in_(order))
    ).all()
    by = {r[0]: r[1] for r in rows}
    return [by[s] for s in order if by.get(s)]


def _category_for(db: Session, cover_slug: str | None, cited: list[str]) -> str | None:
    slug = cover_slug or (cited[0] if cited else None)
    if not slug:
        return None
    show = db.get(Show, slug)
    return getattr(show.category, "value", show.category) if show else None


def _attach_covers(db: Session, post: BlogPost, cover_slug: str | None,
                   cited: list[str]) -> None:
    poster_urls = _poster_urls(db, cover_slug, cited)
    category = _category_for(db, cover_slug, cited)
    imgs = covers.render_post_images(
        post.id, post.title, post.kicker, category, poster_urls,
        focus_y=post.cover_focus_y or 50,
    )
    if imgs.get("cover_image_url"):
        post.cover_image_url = imgs["cover_image_url"]
    if imgs.get("share_image_url"):
        post.share_image_url = imgs["share_image_url"]


# --- Form value shaping ---------------------------------------------------


def _form_values(**kw) -> dict:
    base = {
        "title": "", "slug": "", "excerpt": "", "tldr": "", "body_html": "",
        "cover_image_url": "", "share_image_url": "", "kicker": "",
        "cover_focus_y": 50,
        "list_items_json": "", "faq_json": "", "author": "BingeTime",
        "status": PostStatus.draft.value, "publish_at": "",
    }
    base.update(kw)
    return base


def _values_of(post: BlogPost) -> dict:
    return _form_values(
        title=post.title,
        slug=post.id,
        excerpt=post.excerpt or "",
        tldr=post.tldr or "",
        # Prettify for the editor so one-line bodies read as paragraphs.
        body_html=blog_lint.prettify_html(post.body_html),
        cover_image_url=post.cover_image_url or "",
        share_image_url=post.share_image_url or "",
        kicker=post.kicker or "",
        cover_focus_y=post.cover_focus_y,
        list_items_json=json.dumps(post.list_items, indent=2) if post.list_items else "",
        faq_json=json.dumps(post.faq, indent=2) if post.faq else "",
        author=post.author,
        status=post.status.value,
        publish_at=(
            post.published_at.strftime("%Y-%m-%dT%H:%M") if post.published_at else ""
        ),
    )


def _render_form(request: Request, *, post, values: dict, error: str | None = None,
                 status_code: int = 200):
    # Slug is editable while the post is a draft (never public yet); it locks
    # at first publish so live URLs / inbound links stay stable.
    can_edit_slug = post is None or post.state == "draft"
    return templates.TemplateResponse(
        request,
        "account_blog_form.html",
        {
            "title": "Edit post" if post else "New post",
            "post": post,
            "values": values,
            "statuses": _STATUS_VALUES,
            "error": error,
            "can_edit_slug": can_edit_slug,
        },
        status_code=status_code,
    )


def _render_list(request: Request, db: Session, *, suggestions=None,
                 notice: str | None = None, error: str | None = None,
                 form: dict | None = None):
    posts = (
        db.execute(select(BlogPost).order_by(BlogPost.updated_at.desc()))
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "account_blog_list.html",
        {
            "title": "Blog posts",
            "posts": posts,
            "agent_enabled": settings.blog_agent_enabled,
            "styles": blog_agent.STYLES,
            "lengths": blog_agent.LENGTHS,
            "suggestions": suggestions,
            "notice": notice,
            "error": error,
            "form": form or {},
        },
    )


# --- List -----------------------------------------------------------------


@router.get("")
def list_posts(request: Request, db: Session = Depends(get_db)):
    if (deny := _admin_guard(request)) is not None:
        return deny
    return _render_list(request, db)


# --- Content agent: suggest / generate / regenerate -----------------------


@router.post("/suggest")
def suggest_titles(request: Request, db: Session = Depends(get_db)):
    if (deny := _admin_guard(request)) is not None:
        return deny
    if not settings.blog_agent_enabled:
        return _render_list(request, db, error="Content agent isn't configured.")
    try:
        suggestions = blog_agent.suggest_titles(db, n=5)
    except blog_agent.BlogAgentError as e:
        return _render_list(request, db, error=str(e))
    notice = None if suggestions else "No fresh angles came back — try again."
    return _render_list(request, db, suggestions=suggestions, notice=notice)


@router.post("/generate")
def generate_post(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(default=""),
    style: str = Form(default="educational"),
    length: str = Form(default="medium"),
    shows: str = Form(default=""),  # optional CSV of anchor slugs from a suggestion
    context: str = Form(default=""),  # optional personal framing for this draft only
):
    if (deny := _admin_guard(request)) is not None:
        return deny
    # Headline-case a hand-typed title so it reads like an auto-generated one.
    title = blog_lint.headline_case(title)
    context = context.strip()
    form = {"title": title, "style": style, "length": length, "context": context}
    if not settings.blog_agent_enabled:
        return _render_list(request, db, error="Content agent isn't configured.",
                            form=form)
    if not title:
        return _render_list(request, db, error="Pick a suggested title or type one.",
                            form=form)
    anchor = [s.strip() for s in shows.split(",") if s.strip()]
    try:
        fields = blog_agent.generate_draft(db, title, style, length,
                                           anchor_shows=anchor, context=context)
    except blog_agent.BlogAgentError as e:
        return _render_list(request, db, error=f"Generation failed: {e}", form=form)

    post = BlogPost(
        id=_unique_slug(db, slugify(fields["title"])),
        title=fields["title"],
        tldr=fields["tldr"],
        body_html=fields["body_html"],
        excerpt=fields["excerpt"],
        kicker=fields["kicker"],
        list_items=fields["list_items"],
        faq=fields["faq"],
        author="BingeTime",
        source="agent",
        review_flags=fields["review_flags"],
        gen_meta=fields["gen_meta"],
        status=PostStatus.draft,
    )
    db.add(post)
    db.flush()  # assign so cover filenames + FK-free PK exist
    _attach_covers(db, post, fields.get("cover_show"), fields.get("shows_cited") or [])
    db.commit()
    return _redirect(f"/account/blog/{post.id}/edit")


@router.post("/{post_id}/regenerate")
def regenerate_post(
    request: Request,
    post_id: str,
    db: Session = Depends(get_db),
    style: str = Form(default=""),
    length: str = Form(default=""),
):
    if (deny := _admin_guard(request)) is not None:
        return deny
    post = db.get(BlogPost, post_id)
    if post is None:
        return templates.TemplateResponse(
            request, "404.html", {"title": "Not found"}, status_code=404
        )
    if not settings.blog_agent_enabled:
        return _render_form(request, post=post, values=_values_of(post),
                            error="Content agent isn't configured.")
    meta = post.gen_meta or {}
    style = style or meta.get("style", "educational")
    length = length or meta.get("length", "medium")
    try:
        fields = blog_agent.generate_draft(db, post.title, style, length)
    except blog_agent.BlogAgentError as e:
        return _render_form(request, post=post, values=_values_of(post),
                            error=f"Regeneration failed: {e}")

    # Replace generated content; keep slug, status, schedule, author.
    post.tldr = fields["tldr"]
    post.body_html = fields["body_html"]
    post.excerpt = fields["excerpt"]
    post.kicker = fields["kicker"]
    post.list_items = fields["list_items"]
    post.faq = fields["faq"]
    post.review_flags = fields["review_flags"]
    post.gen_meta = fields["gen_meta"]
    post.source = "agent"
    _attach_covers(db, post, fields.get("cover_show"), fields.get("shows_cited") or [])
    db.commit()
    return _redirect(f"/account/blog/{post.id}/edit")


@router.post("/{post_id}/cover")
def rebuild_cover(
    request: Request,
    post_id: str,
    db: Session = Depends(get_db),
    cover_show: str = Form(default=""),
    kicker: str = Form(default=""),
    cover_focus_y: int = Form(default=50),
):
    """Recompose just the cover + OG image from a chosen show's poster (no LLM),
    so a bad auto-pick is a one-click fix."""
    if (deny := _admin_guard(request)) is not None:
        return deny
    post = db.get(BlogPost, post_id)
    if post is None:
        return templates.TemplateResponse(
            request, "404.html", {"title": "Not found"}, status_code=404
        )
    if kicker.strip():
        post.kicker = kicker.strip()[:40]
    # Set the focal point before recomposing so the new crop honors it.
    post.cover_focus_y = max(0, min(100, cover_focus_y))
    slug = cover_show.strip() or None
    cited = (post.gen_meta or {}).get("shows_cited") or []
    # A specific pick → a single hero poster; otherwise the post's cited shows.
    _attach_covers(db, post, slug, [slug] if slug else cited)
    if post.gen_meta is not None and slug:
        post.gen_meta = {**post.gen_meta, "cover_show": slug}
    db.commit()
    return _redirect(f"/account/blog/{post_id}/edit")


# --- Manual create --------------------------------------------------------


@router.get("/new")
def new_post_form(request: Request):
    if (deny := _admin_guard(request)) is not None:
        return deny
    return _render_form(request, post=None, values=_form_values())


@router.post("/new")
def create_post(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(default=""),
    slug: str = Form(default=""),
    excerpt: str = Form(default=""),
    tldr: str = Form(default=""),
    body_html: str = Form(default=""),
    cover_image_url: str = Form(default=""),
    kicker: str = Form(default=""),
    author: str = Form(default="BingeTime"),
    status: str = Form(default=PostStatus.draft.value),
    publish_at: str = Form(default=""),
):
    if (deny := _admin_guard(request)) is not None:
        return deny
    title = title.strip()
    final_slug = slugify(slug or title)
    values = _form_values(
        title=title, slug=slug, excerpt=excerpt, tldr=tldr, body_html=body_html,
        cover_image_url=cover_image_url, kicker=kicker, author=author,
        status=status, publish_at=publish_at,
    )
    error = None
    if not title:
        error = "A title is required."
    elif not body_html.strip():
        error = "The post body can't be empty."
    elif not final_slug:
        error = "Enter a slug with at least one letter or number."
    elif db.get(BlogPost, final_slug) is not None:
        error = f"The slug '{final_slug}' is already taken — pick another."
    if error:
        return _render_form(request, post=None, values=values, error=error,
                            status_code=400)

    post = BlogPost(
        id=final_slug, title=title, excerpt=excerpt.strip() or None,
        tldr=tldr.strip() or None, body_html=body_html,
        cover_image_url=cover_image_url.strip() or None, kicker=kicker.strip() or None,
        author=author.strip() or "BingeTime", source="manual",
    )
    _apply_status(post, status, _parse_publish_at(publish_at))
    db.add(post)
    db.commit()
    return _redirect("/account/blog")


# --- Edit -----------------------------------------------------------------


@router.get("/{post_id}/edit")
def edit_post_form(request: Request, post_id: str, db: Session = Depends(get_db)):
    if (deny := _admin_guard(request)) is not None:
        return deny
    post = db.get(BlogPost, post_id)
    if post is None:
        return templates.TemplateResponse(
            request, "404.html", {"title": "Not found"}, status_code=404
        )
    return _render_form(request, post=post, values=_values_of(post))


@router.post("/{post_id}/edit")
def update_post(
    request: Request,
    post_id: str,
    db: Session = Depends(get_db),
    title: str = Form(default=""),
    slug: str = Form(default=""),
    excerpt: str = Form(default=""),
    tldr: str = Form(default=""),
    body_html: str = Form(default=""),
    cover_image_url: str = Form(default=""),
    share_image_url: str = Form(default=""),
    kicker: str = Form(default=""),
    cover_focus_y: int = Form(default=50),
    list_items_json: str = Form(default=""),
    faq_json: str = Form(default=""),
    author: str = Form(default="BingeTime"),
    status: str = Form(default=PostStatus.draft.value),
    publish_at: str = Form(default=""),
):
    if (deny := _admin_guard(request)) is not None:
        return deny
    post = db.get(BlogPost, post_id)
    if post is None:
        return templates.TemplateResponse(
            request, "404.html", {"title": "Not found"}, status_code=404
        )

    title = title.strip()
    cover_focus_y = max(0, min(100, cover_focus_y))
    values = _form_values(
        title=title, slug=slug or post.id, excerpt=excerpt, tldr=tldr,
        body_html=body_html, cover_image_url=cover_image_url,
        share_image_url=share_image_url, kicker=kicker,
        cover_focus_y=cover_focus_y,
        list_items_json=list_items_json, faq_json=faq_json, author=author,
        status=status, publish_at=publish_at,
    )
    error = None
    if not title:
        error = "A title is required."
    elif not body_html.strip():
        error = "The post body can't be empty."

    # Slug editing is allowed only while the post is still a draft.
    new_slug = post.id
    if post.state == "draft" and slug.strip():
        candidate = slugify(slug)
        if not candidate:
            error = error or "Slug needs at least one letter or number."
        elif candidate != post.id and db.get(BlogPost, candidate) is not None:
            error = error or f"The slug '{candidate}' is already taken."
        else:
            new_slug = candidate

    if error:
        return _render_form(request, post=post, values=values, error=error,
                            status_code=400)

    post.title = blog_lint.clean_text(title) or title
    post.excerpt = blog_lint.clean_text(excerpt) or None
    post.tldr = blog_lint.clean_text(tldr) or None
    post.body_html = body_html
    post.cover_image_url = cover_image_url.strip() or None
    post.share_image_url = share_image_url.strip() or None
    post.cover_focus_y = cover_focus_y
    post.kicker = blog_lint.clean_text(kicker) or None
    post.list_items = _parse_json_field(list_items_json)
    post.faq = _parse_json_field(faq_json)
    post.author = author.strip() or "BingeTime"
    _apply_status(post, status, _parse_publish_at(publish_at))
    if new_slug != post.id:
        post.id = new_slug  # no FKs reference blog_posts → PK update is safe
    db.commit()
    return _redirect("/account/blog")


# --- Delete ---------------------------------------------------------------


@router.post("/{post_id}/delete")
def delete_post(request: Request, post_id: str, db: Session = Depends(get_db)):
    if (deny := _admin_guard(request)) is not None:
        return deny
    post = db.get(BlogPost, post_id)
    if post is not None:
        db.delete(post)
        db.commit()
    return _redirect("/account/blog")
