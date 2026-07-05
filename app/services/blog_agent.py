"""The blog content agent: title ideation + grounded draft generation.

Calls Claude with a cached system prompt (voice + hard rules + output
contract), parses a JSON contract with one corrective retry, then hands the
result to blog_lint for deterministic enforcement. See
docs/blog-content-agent-spec.md. Model + key come from settings; the anti-slop
voice is prompt-driven only (these models reject `temperature`).
"""
from __future__ import annotations

import json
import random
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import BlogPost
from . import blog_data, blog_lint

STYLES = ["funny", "educational", "roast", "hype", "chill"]
LENGTHS = ["short", "medium", "long", "surprise"]
_LEN_BASE = {"short": 300, "medium": 600, "long": 900}


class BlogAgentError(RuntimeError):
    """Raised when generation can't be completed (misconfig, API, or bad output)."""


# --- System prompt (stable → prompt-cached) -------------------------------

SYSTEM_PROMPT = """\
You write the blog for BingeTime (bingetime.tv), a site that tells people \
exactly how long it takes to binge any show, shows the original viral \
video breakdown, and helps them plan their watch schedule. You write as the \
BingeTime brand voice. Your job is SEO + AEO content that ranks and gets cited.

# VOICE (always on)
Casual, informal, authentic. Sound like an avid TV fan talking to a friend, \
not a press release. Slang, jokes, real opinions, varied sentence length, the \
occasional fragment for rhythm. Vary your rhythm deliberately. Do NOT write in \
a robotic, uniform, over-polished AI cadence. Banned openers and filler: "Let's \
dive in", "Here's the thing", "In this article", "In conclusion", "Buckle up", \
"Without further ado". Imperfect rhythm is good; typos and broken grammar are not.

# STYLE (applied per request)
- funny: jokes-forward, playful exaggeration.
- educational: explainer energy, still casual, teach something.
- roast: spicy, take shots at the SHOW, never at real people (no attacks on \
actors/creators). Playful, never cruel or defamatory.
- hype: enthusiastic, "you have to watch this".
- chill: laid-back, low-key, understated.
Structure is the skeleton, style is the paint: never let personality bury the \
direct answer or the data.

# HARD RULES (non-negotiable)
1. ZERO EM-DASHES. Never use the em dash, en dash, or double hyphen anywhere. \
Use commas, periods, or parentheses instead. This is absolute.
2. DATA MOAT. Every number/metric you state (runtime, episode count, seasons, \
year, rating) MUST come verbatim from the DATA payload provided. Never invent a \
number. Never do your own arithmetic: do not sum, average, or total values \
yourself. Only state a total/average if it is explicitly provided in the \
aggregates. Opinions and stances are encouraged and unrestricted, but facts and \
figures are locked to the data.
3. SHOW LINKS. The body is raw HTML. Every show from the catalog that you \
reference, wrap its FIRST mention only in <x-show slug='THE-SLUG'>Show Title</x-show> \
using the exact slug from the data. Do not wrap later mentions. Only wrap shows \
that appear in the data (they have a slug); shows not in the catalog may be \
named in plain text but carry no stats.
4. LENGTH is a target, not a quota. Never pad to hit a word count. If the \
angle is thin, write short and tight.

# AEO (get cited by AI answer engines)
Return a clean, direct answer to the post's implied question (1 to 3 sentences) \
as `tldr`. It renders as the lead, so DO NOT repeat it in body_html: start the \
body with the supporting content. For ranked/list posts, ALSO return the ranked \
items as structured `list_items` (each with the real value from the data) as \
well as writing them out in the body. Add 2 to 4 genuinely useful `faq` Q/A \
pairs when they fit; the FAQ renders as its own section, so do NOT repeat it \
inside body_html.

# HTML
Use only these tags in body_html: p, h2, h3, ul, ol, li, a, strong, em, \
blockquote, br, img, table, thead, tbody, tr, th, td (plus the x-show wrapper). \
No inline styles, scripts, or other tags.

# JSON SAFETY (critical)
Your entire response is parsed as JSON, so:
- NEVER use the straight double-quote character anywhere inside any string \
value. Use single quotes for all HTML attributes (e.g. <x-show slug='one-piece'>) \
and single quotes or curly quotes in prose.
- body_html must be a SINGLE line with no literal line breaks (the HTML tags \
provide the structure).
- ONLY body_html may contain HTML or <x-show> tags. tldr, excerpt, kicker, \
list_items, and faq must be PLAIN TEXT with no tags at all (name shows in plain \
words there).

# OUTPUT
Respond with a SINGLE JSON object and nothing else (no prose, no markdown \
fences). Shapes:

For TASK=titles:
{"titles": [
  {"title": "...", "archetype": "list|study|trending|opinion",
   "shows": ["slug", ...], "count": <int or null>, "angle": "one-line why"},
  ... exactly N items
]}
- Ground every title in real data. For list/study angles the shows array must \
list the real shows it will cover and count must equal their number. Do not \
propose an angle that duplicates an existing post (a list is provided).

For TASK=draft:
{"tldr": "...", "body_html": "...", "excerpt": "<=200 chars",
 "kicker": "2-4 word cover label, e.g. WEEKEND BINGE",
 "cover_show": "slug or null", "shows_cited": ["slug", ...],
 "list_items": [{"show_slug": "slug or null", "value": "e.g. 42h", "note": "..."}],
 "faq": [{"q": "...", "a": "..."}]}
- list_items and faq may be empty arrays if not applicable.
- cover_show should be a show central to the post (for the cover image).
"""


# --- Anthropic call -------------------------------------------------------


def _client():
    if not settings.blog_agent_enabled:
        raise BlogAgentError(
            "Blog agent is not configured (set CLAUDE_BLOG_AGENT_API_KEY)."
        )
    import anthropic

    return anthropic.Anthropic(api_key=settings.claude_blog_agent_api_key)


def _complete(user_text: str, effort: str, max_tokens: int) -> str:
    """One streamed completion; returns concatenated text (thinking ignored)."""
    client = _client()
    try:
        with client.messages.stream(
            model=settings.blog_agent_model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": user_text}],
        ) as stream:
            msg = stream.get_final_message()
    except Exception as e:  # surface API errors to the admin UI, don't 500
        raise BlogAgentError(f"Claude request failed: {e}") from e
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\n?|\n?```$")


def _extract_json(text: str) -> dict:
    t = text.strip()
    t = _FENCE_RE.sub("", t).strip()
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        t = t[i : j + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        raise BlogAgentError(f"Model did not return valid JSON: {e}") from e


# --- Title ideation -------------------------------------------------------


def _existing_posts(db: Session) -> list[dict]:
    rows = db.execute(select(BlogPost.id, BlogPost.title)).all()
    return [{"slug": r[0], "title": r[1]} for r in rows]


def suggest_titles(db: Session, n: int = 5) -> list[dict]:
    catalog = blog_data.compact_catalog(db)
    trending = blog_data.trending_slugs(db, 12)
    aggregates = blog_data.catalog_aggregates(db)
    existing = _existing_posts(db)

    user = (
        "TASK=titles\n"
        f"Suggest exactly {n} blog title ideas. Lean data-first (list/study/"
        "trending); at most one opinion angle. Prefer angles that ride the "
        "TRENDING shows or that our data can uniquely answer.\n\n"
        f"TRENDING_SLUGS (demand signal): {json.dumps(trending)}\n\n"
        f"AGGREGATES: {json.dumps(aggregates)}\n\n"
        f"EXISTING_POSTS (do not duplicate): "
        f"{json.dumps([e['title'] for e in existing])}\n\n"
        f"CATALOG: {json.dumps(catalog)}"
    )
    data = _extract_json(_complete(user, settings.blog_agent_title_effort, 3500))
    return _clean_titles(db, data.get("titles", []), existing, n)


def _clean_titles(
    db: Session, raw: list, existing: list[dict], n: int
) -> list[dict]:
    existing_titles = {e["title"].strip().lower() for e in existing}
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = blog_lint.clean_text(item.get("title", ""))
        key = title.lower()
        if not title or key in existing_titles or key in seen:
            continue
        shows = [s for s in (item.get("shows") or []) if isinstance(s, str)]
        valid = blog_data.valid_slugs(db, shows)
        shows = [s for s in shows if s in valid]  # keep only real ones
        seen.add(key)
        out.append(
            {
                "title": title,
                "archetype": item.get("archetype", "list"),
                "shows": shows,
                "count": len(shows) if shows else None,
                "angle": blog_lint.clean_text(item.get("angle", "")),
            }
        )
        if len(out) >= n:
            break
    return out


# --- Draft generation -----------------------------------------------------


def _length_target(length_key: str) -> int:
    if length_key == "surprise":
        return random.randint(300, 1000)
    return _LEN_BASE.get(length_key, 600) + random.randint(-75, 75)


_JSON_NUDGE = (
    "Your previous output was not valid JSON. Respond with ONLY one valid JSON "
    "object, no prose or code fences, and never use a straight double-quote "
    "inside any string (single-quote all HTML attributes; keep body_html on one line)."
)


def _draft_call(
    db: Session, title: str, style: str, target: int,
    anchor_shows: list[str], correction: str = "",
) -> dict:
    catalog = blog_data.compact_catalog(db)
    aggregates = blog_data.catalog_aggregates(db)
    anchor = blog_data.citable_shows(db, anchor_shows) if anchor_shows else []
    user = (
        "TASK=draft\n"
        f"TITLE: {title}\n"
        f"STYLE: {style}\n"
        f"TARGET_WORDS: about {target} (a target, never pad)\n\n"
        + (f"ANCHOR_SHOWS (build the post around these): {json.dumps(anchor)}\n\n"
           if anchor else "")
        + f"AGGREGATES: {json.dumps(aggregates)}\n\n"
        f"CATALOG (cite any of these by slug; these are the only real numbers): "
        f"{json.dumps(catalog)}"
        + (f"\n\nCORRECTION: {correction}" if correction else "")
    )
    effort = settings.blog_agent_draft_effort
    raw = _complete(user, effort, 8000)
    try:
        return _extract_json(raw)
    except BlogAgentError:
        # One self-heal retry for a malformed-JSON hiccup (stray quote/newline).
        raw = _complete(user + "\n\n" + _JSON_NUDGE, effort, 8000)
        return _extract_json(raw)


def generate_draft(
    db: Session, title: str, style: str, length_key: str,
    anchor_shows: list[str] | None = None,
) -> dict:
    """Generate + finalize one post. Returns a dict of BlogPost field values
    (id/slug not set here) plus `review_flags`. Raises BlogAgentError on failure."""
    if style not in STYLES:
        style = "educational"
    if length_key not in LENGTHS:
        length_key = "medium"
    target = _length_target(length_key)
    anchor_shows = anchor_shows or []

    data = _draft_call(db, title, style, target, anchor_shows)

    # Retry once if the model tripped a hard rule we can detect pre-cleanup.
    raw_text = " ".join(
        str(data.get(k, "")) for k in ("tldr", "excerpt", "kicker", "body_html")
    )
    cited = [s for s in (data.get("shows_cited") or []) if isinstance(s, str)]
    invalid_cited = set(cited) - blog_data.valid_slugs(db, cited)
    if blog_lint.has_banned_dash(raw_text) or invalid_cited:
        issues = []
        if blog_lint.has_banned_dash(raw_text):
            issues.append("you used a banned dash (em/en/double-hyphen)")
        if invalid_cited:
            issues.append(
                f"these slugs are not in the catalog: {', '.join(invalid_cited)}"
            )
        correction = "Fix and re-output the full JSON: " + "; ".join(issues) + "."
        try:
            data = _draft_call(db, title, style, target, anchor_shows, correction)
        except BlogAgentError:
            pass  # keep the first draft; the deterministic finalizer cleans it

    return _finalize(db, data, title, style, length_key, target)


def _finalize(
    db: Session, data: dict, title: str, style: str, length_key: str, target: int
) -> dict:
    flags: list[str] = []

    # Collect every slug the post references, validate against the catalog.
    cited = [s for s in (data.get("shows_cited") or []) if isinstance(s, str)]
    li_slugs = [
        it.get("show_slug")
        for it in (data.get("list_items") or [])
        if isinstance(it, dict) and it.get("show_slug")
    ]
    valid = blog_data.valid_slugs(db, cited + li_slugs)

    body, body_flags = blog_lint.finalize_body(data.get("body_html", ""), valid)
    flags += body_flags

    # Clean list_items: null out invalid slugs (keep the row), attach the real
    # show title, dash-normalize.
    titles = blog_data.slug_titles(db, sorted(valid))
    list_items = []
    for it in (data.get("list_items") or []):
        if not isinstance(it, dict):
            continue
        slug = it.get("show_slug")
        if slug and slug not in valid:
            flags.append(f"list item dropped invalid slug: {slug}")
            slug = None
        list_items.append(
            {
                "show_slug": slug,
                "title": titles.get(slug) if slug else None,
                "value": blog_lint.clean_text(str(it.get("value", ""))),
                "note": blog_lint.clean_text(str(it.get("note", ""))),
            }
        )

    faq = []
    for qa in (data.get("faq") or []):
        if isinstance(qa, dict) and qa.get("q") and qa.get("a"):
            faq.append(
                {
                    "q": blog_lint.clean_text(str(qa["q"])),
                    "a": blog_lint.clean_text(str(qa["a"])),
                }
            )

    cover_show = data.get("cover_show")
    if cover_show and cover_show not in valid:
        cover_show = None

    return {
        "title": blog_lint.clean_text(title),
        "tldr": blog_lint.clean_text(str(data.get("tldr", ""))) or None,
        "body_html": body,
        "excerpt": blog_lint.clean_text(str(data.get("excerpt", "")))[:280] or None,
        "kicker": blog_lint.clean_text(str(data.get("kicker", "")))[:40] or None,
        "list_items": list_items or None,
        "faq": faq or None,
        "cover_show": cover_show,
        "shows_cited": sorted(valid) or None,
        "review_flags": flags or None,
        "gen_meta": {
            "style": style,
            "length": length_key,
            "target_words": target,
            "model": settings.blog_agent_model,
            "effort": settings.blog_agent_draft_effort,
            # Kept so the admin cover control can offer the post's shows and
            # remember which one the cover was built from.
            "cover_show": cover_show,
            "shows_cited": sorted(valid),
        },
    }
