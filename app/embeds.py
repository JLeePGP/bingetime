"""Turn a creator video URL into the data a template needs to embed it."""
from __future__ import annotations

import re
from dataclasses import dataclass

_YT_SHORTS = re.compile(r"youtube\.com/shorts/([\w-]+)")
_YT_WATCH = re.compile(r"[?&]v=([\w-]+)")
_YT_SHORT_LINK = re.compile(r"youtu\.be/([\w-]+)")
_TIKTOK_ID = re.compile(r"/video/(\d+)")


@dataclass(frozen=True)
class Embed:
    platform: str  # tiktok | youtube | instagram
    url: str
    youtube_id: str | None = None
    tiktok_id: str | None = None


def build_embed(platform: str, url: str) -> Embed:
    platform = (platform or "").lower()
    if platform == "youtube":
        m = _YT_SHORTS.search(url) or _YT_WATCH.search(url) or _YT_SHORT_LINK.search(url)
        return Embed("youtube", url, youtube_id=m.group(1) if m else None)
    if platform == "tiktok":
        m = _TIKTOK_ID.search(url)
        return Embed("tiktok", url, tiktok_id=m.group(1) if m else None)
    return Embed("instagram", url)
