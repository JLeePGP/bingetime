"""Save-time enforcement of the blog agent's hard rules (spec §4, §9, §10).

The prompt asks for these; this module *guarantees* them: zero em-dashes,
show links that resolve to real catalog slugs (first mention only), and a
tag-allowlisted body. Everything here is deterministic and unit-testable.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# --- Em-dash ban ----------------------------------------------------------

# Order matters: entities and spaced forms before bare glyphs so we don't
# leave a stray double-space. Every banned form collapses to a comma.
_DASH_SUBS: list[tuple[str, str]] = [
    ("&mdash;", ", "), ("&#8212;", ", "),
    ("&ndash;", ", "), ("&#8211;", ", "),
    (" — ", ", "), (" – ", ", "),
    ("—", ", "), ("–", ", "),
    (" -- ", ", "), ("--", ", "),
]
_BANNED_DASH_RE = re.compile(r"—|–|--|&mdash;|&ndash;|&#8212;|&#8211;")


def has_banned_dash(text: str | None) -> bool:
    return bool(text) and bool(_BANNED_DASH_RE.search(text))


def normalize_dashes(text: str | None) -> str:
    """Strip every banned dash form (fallback after the model's retry)."""
    if not text:
        return text or ""
    out = text
    for bad, good in _DASH_SUBS:
        out = out.replace(bad, good)
    # Tidy any doubled punctuation the substitution may have created.
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


# Short fields (title, tldr, excerpt, kicker, faq, list items) are plain text.
# Strip any HTML the model slipped in — notably <x-show> markers, which only
# belong in body_html. Anchored to known tag names so stray < / > in prose
# (e.g. "under < 20 hrs") survive. Unwrapping keeps the inner label text.
_STRIP_TAG_RE = re.compile(
    r"</?(?:x-show|p|h[1-6]|a|strong|em|b|i|u|ul|ol|li|br|img|blockquote|"
    r"span|div|table|thead|tbody|tr|th|td)\b[^>]*>",
    re.IGNORECASE,
)


def clean_text(text: str | None) -> str:
    """Strip stray HTML, dash-normalize, and trim a short plain-text field."""
    stripped = _STRIP_TAG_RE.sub("", text or "")
    return normalize_dashes(stripped).strip()


# Short words kept lowercase mid-title (headline style), matching how the agent
# already casts its own titles.
_MINOR_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "if", "in", "into", "nor",
    "of", "off", "on", "or", "per", "so", "the", "to", "up", "via", "vs", "yet",
    "with", "from", "than", "that",
}


def _cap_word(word: str) -> str:
    """Capitalize the first letter (leaving the rest as typed); handle hyphens
    and preserve all-caps acronyms (MCU, TV)."""
    if word.isupper() and len(word) > 1:
        return word
    return "-".join(
        (p[:1].upper() + p[1:]) if p else p for p in word.split("-")
    )


def headline_case(text: str | None) -> str:
    """Title-case a hand-typed title the way an auto-generated one reads: cap
    every significant word, keep minor words lowercase except the first/last
    word or right after a colon."""
    words = (text or "").strip().split()
    if not words:
        return ""
    last = len(words) - 1
    out: list[str] = []
    after_break = True  # first word behaves like a sentence start
    for i, w in enumerate(words):
        bare = w.lower().strip(",:;.!?'\"")
        if after_break or i == last or bare not in _MINOR_WORDS:
            out.append(_cap_word(w))
        elif w.isupper() and len(w) > 1:
            out.append(w)  # keep acronym
        else:
            out.append(w.lower())
        after_break = w.endswith((":", "?", "!", "."))
    return " ".join(out)


# --- Show-link expansion (first mention only, validated) ------------------

_SHOW_TAG_RE = re.compile(
    r"""<x-show\s+slug=['"](?P<slug>[^'"]+)['"]\s*>(?P<label>.*?)</x-show>""",
    re.IGNORECASE | re.DOTALL,
)


def expand_show_links(html: str, valid: set[str]) -> tuple[str, list[str]]:
    """Turn <x-show slug="…">Label</x-show> markers into anchors.

    First valid mention of a slug becomes a link; later mentions of the same
    slug and any invalid slug become plain text. Returns (html, invalid_slugs).
    """
    linked: set[str] = set()
    invalid: list[str] = []

    def repl(m: re.Match) -> str:
        slug = m.group("slug").strip()
        label = m.group("label")
        if slug not in valid:
            if slug not in invalid:
                invalid.append(slug)
            return label
        if slug in linked:
            return label
        linked.add(slug)
        return f'<a href="/shows/{slug}">{label}</a>'

    return _SHOW_TAG_RE.sub(repl, html), invalid


# --- HTML sanitize (tag allowlist) ----------------------------------------

_ALLOWED_TAGS = {
    "p", "h2", "h3", "ul", "ol", "li", "a", "strong", "em", "blockquote",
    "br", "img", "table", "thead", "tbody", "tr", "th", "td",
}
_VOID_TAGS = {"br", "img"}
_ALLOWED_ATTRS = {"a": {"href"}, "img": {"src", "alt"}}
# Disallowed tags are unwrapped (their text is kept), except these whose
# *content* must be dropped entirely.
_DROP_CONTENT_TAGS = {"script", "style", "template", "noscript"}


def _safe_url(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith("/") or v.startswith("https://") or v.startswith("http://")


class _Sanitizer(HTMLParser):
    """Rebuild HTML keeping only allowlisted tags/attrs; disallowed tags are
    dropped but their text content is preserved."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._drop_depth = 0  # >0 while inside a script/style/etc. subtree

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if tag not in _ALLOWED_TAGS:
            return
        kept = []
        for name, val in attrs:
            if val is not None and name in _ALLOWED_ATTRS.get(tag, set()):
                if name in ("href", "src") and not _safe_url(val):
                    continue
                kept.append(f' {name}="{_escape_attr(val)}"')
        slash = "" if tag not in _VOID_TAGS else " /"
        self.out.append(f"<{tag}{''.join(kept)}{slash}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._drop_depth == 0:
            self.out.append(_escape_text(data))

    def result(self) -> str:
        return "".join(self.out)


def _escape_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s: str) -> str:
    return _escape_text(s).replace('"', "&quot;")


def sanitize_html(html: str) -> str:
    p = _Sanitizer()
    p.feed(html or "")
    p.close()
    return p.result()


# --- Top-level finalizer --------------------------------------------------


# Block-level tags that read best each on their own line in the editor.
_BLOCK_CLOSE_RE = re.compile(
    r"(</(?:p|h2|h3|li|ul|ol|blockquote|tr|table|thead|tbody)>)", re.IGNORECASE
)


def prettify_html(html: str) -> str:
    """Put each block-level element on its own line so the editor textarea is
    readable. Purely cosmetic — the rendered page is unaffected by the newlines.
    Idempotent."""
    out = _BLOCK_CLOSE_RE.sub(r"\1\n", html or "")
    return re.sub(r"\n{2,}", "\n", out).strip()


def finalize_body(html: str, valid_slugs: set[str]) -> tuple[str, list[str]]:
    """Expand show links, normalize dashes, sanitize, prettify. Returns (html, flags)."""
    flags: list[str] = []
    body, invalid = expand_show_links(html or "", valid_slugs)
    if invalid:
        flags.append(f"unlinked invalid show slug(s): {', '.join(invalid)}")
    if has_banned_dash(body):
        flags.append("em-dash auto-removed from body")
    body = normalize_dashes(body)
    body = sanitize_html(body)
    return prettify_html(body), flags
