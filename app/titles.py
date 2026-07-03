"""Slug -> human title, shared by import and TMDB enrichment.

Enrichment must search by a *stable* key (derived from the immutable slug),
never the stored title, or a re-run would search a previously-corrected name
and drift. This is that stable derivation.
"""
from __future__ import annotations

import re
import unicodedata

# Slugs whose naive title-case is wrong; placeholder until TMDB confirms.
TITLE_OVERRIDES = {
    "jojos-bizarre-adventure": "JoJo's Bizarre Adventure",
    "greys-anatomy": "Grey's Anatomy",
    "brooklyn-nine-nine": "Brooklyn Nine-Nine",
    "spongebob": "SpongeBob SquarePants",
    "jojo": "JoJo's Bizarre Adventure",
    "kaiju-no-8": "Kaiju No. 8",
    "one-punch-man": "One-Punch Man",
}

# For irreducibly ambiguous one-word slugs, pin the exact TMDB search term
# (and the exact-match ranking then locks onto the right entry). Add entries
# here as John confirms which show each creator video actually covers.
SEARCH_OVERRIDES: dict[str, str] = {
    "fate": "Fate/stay night",  # franchise anchor — see note in README
    "gundam": "Mobile Suit Gundam",  # the original 1979 series
}

_ARTICLES = ("the ", "a ", "an ")


def humanize(slug: str) -> str:
    if slug in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[slug]
    return slug.replace("-", " ").title()


def search_title(slug: str) -> str:
    """The title to query TMDB with — an explicit override if set, else the
    humanized slug."""
    return SEARCH_OVERRIDES.get(slug) or humanize(slug)


def normalize(name: str) -> str:
    """Casefold, strip accents, fold punctuation to spaces, and drop a leading
    article for tolerant title comparison: 'Pokémon' == 'pokemon',
    'Fate/stay night' == 'Fate stay night', 'Seven Deadly Sins' == 'The Seven
    Deadly Sins'."""
    s = (name or "").strip().casefold()
    s = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    for art in _ARTICLES:
        if s.startswith(art):
            return s[len(art):]
    return s
