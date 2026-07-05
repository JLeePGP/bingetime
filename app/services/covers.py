"""Compose blog cover + OG share images with Pillow (spec §12).

On-site cover = imagery only (poster backdrop + gradient + category tint +
short kicker), never the title (it renders right below the card). The
title-bearing card is generated separately as the OG/social share image.

Everything is best-effort: a poster fetch or font failure falls back to a
brand-gradient card so a post always gets an image. Only a hard Pillow failure
returns None (the caller then leaves the field unset).
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

# Generated media lives outside the committed static tree, under /media, which
# is served by its own mount and can be backed by a Railway volume so cover
# images survive redeploys (the container filesystem is otherwise ephemeral).
_OUT_DIR = Path(__file__).resolve().parent.parent.parent / "media" / "blog"

COVER_SIZE = (1200, 675)   # 16:9, matches .blog-card-cover
SHARE_SIZE = (1200, 630)   # OG standard

_BG_TOP = (14, 13, 20)
_CATEGORY_RGB = {
    "movie": (74, 144, 226),
    "tv": (108, 92, 231),
    "anime": (255, 77, 109),
}
_DEFAULT_TINT = (108, 92, 231)


def _tint(category: str | None) -> tuple[int, int, int]:
    return _CATEGORY_RGB.get((category or "").lower(), _DEFAULT_TINT)


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)  # scalable default (Pillow ≥10.1)
    except TypeError:
        return ImageFont.load_default()


def _fetch_poster(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        r = httpx.get(url, timeout=8.0, follow_redirects=True)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _cover_fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + center-crop to fill `size` (object-fit: cover)."""
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _backdrop(size: tuple[int, int], posters: list[Image.Image],
              tint: tuple[int, int, int]) -> Image.Image:
    """Poster hero / collage under a dark gradient, or a brand gradient."""
    w, h = size
    base = Image.new("RGB", size, _BG_TOP)

    if len(posters) >= 2:
        # Collage strip: up to 3 posters side by side.
        cells = posters[:3]
        cw = w // len(cells)
        for i, p in enumerate(cells):
            base.paste(_cover_fit(p, (cw, h)), (i * cw, 0))
    elif posters:
        base.paste(_cover_fit(posters[0], size), (0, 0))
    else:
        # Brand gradient: dark top → tinted dark bottom.
        grad = Image.new("RGB", (1, h))
        for y in range(h):
            t = y / max(1, h - 1)
            grad.putpixel((0, y), tuple(
                int(_BG_TOP[c] + (tint[c] * 0.45 - _BG_TOP[c]) * t) for c in range(3)
            ))
        base = grad.resize(size)

    # Darkening overlay so overlaid text stays readable (stronger at the bottom).
    overlay = Image.new("L", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        overlay.putpixel((0, y), int(90 + 150 * t))
    shade = Image.new("RGB", size, (0, 0, 0))
    base = Image.composite(shade, base, overlay.resize(size))
    return base


def _wrap(draw, text, font, max_w) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _brand_mark(draw, x, y):
    f = _font(30)
    draw.text((x, y), "Binge", font=f, fill=(255, 255, 255))
    w = draw.textlength("Binge", font=f)
    draw.text((x + w, y), "Time", font=f, fill=(255, 77, 109))


def _save(img: Image.Image, name: str) -> str:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(_OUT_DIR / name, "PNG")
    # Version query busts the immutable media cache when a post is regenerated.
    return f"/media/blog/{name}?v={int(time.time())}"


def render_post_images(
    slug: str, title: str, kicker: str | None, category: str | None,
    poster_urls: list[str],
) -> dict:
    """Compose + save both images. Returns {cover_image_url, share_image_url};
    a value is None only if Pillow itself fails."""
    tint = _tint(category)
    posters = [p for p in (_fetch_poster(u) for u in poster_urls[:3]) if p]
    kicker = (kicker or (category or "").upper() or "BINGETIME").strip()[:24]
    result: dict = {"cover_image_url": None, "share_image_url": None}

    # --- On-site cover (imagery only, no title) ---
    try:
        img = _backdrop(COVER_SIZE, posters, tint)
        d = ImageDraw.Draw(img)
        _brand_mark(d, 44, 40)
        # Tint bar + kicker, bottom-left.
        ky = COVER_SIZE[1] - 84
        d.rectangle([44, ky + 6, 52, ky + 40], fill=tint)
        d.text((66, ky), kicker, font=_font(34), fill=(255, 255, 255))
        result["cover_image_url"] = _save(img, f"{slug}-cover.png")
    except Exception:
        pass

    # --- OG share card (title-bearing) ---
    try:
        img = _backdrop(SHARE_SIZE, posters, tint)
        d = ImageDraw.Draw(img)
        _brand_mark(d, 48, 44)
        d.text((48, 96), kicker, font=_font(28), fill=tint)
        tf = _font(60)
        lines = _wrap(d, title, tf, SHARE_SIZE[0] - 96)[:4]
        y = SHARE_SIZE[1] - 60 - len(lines) * 70
        for line in lines:
            d.text((48, y), line, font=tf, fill=(255, 255, 255))
            y += 70
        result["share_image_url"] = _save(img, f"{slug}-share.png")
    except Exception:
        pass

    return result
