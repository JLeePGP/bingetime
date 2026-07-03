"""Watch-time calculator — pure functions, no DB or web dependency.

Given a base runtime in minutes plus a rewatch multiplier and playback
speed, produce the hours/days/weeks breakdown and a shareable stat.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_PER_HOUR = 60
MIN_PER_DAY = 60 * 24
MIN_PER_WEEK = 60 * 24 * 7
MIN_PER_MONTH = 60 * 24 * 30  # 30-day month, for the "months/years" stat
MIN_PER_YEAR = 60 * 24 * 365


@dataclass(frozen=True)
class WatchTime:
    base_runtime_min: int
    times_watched: int
    playback_speed: float
    effective_min: int

    # Decimal views of the same duration.
    hours: float
    days: float
    weeks: float

    # Human "Xd Yh Zm" breakdown of the continuous duration.
    breakdown: str
    # Shareable one-liner, scaled to the largest sensible unit.
    share_stat: str


def _humanize_duration(total_min: int) -> str:
    """e.g. 4890 -> '3d 9h 30m'. Always includes minutes for exactness."""
    if total_min <= 0:
        return "0m"
    days, rem = divmod(total_min, MIN_PER_DAY)
    hours, minutes = divmod(rem, MIN_PER_HOUR)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def _share_stat(effective_min: int) -> str:
    """Largest natural unit for the 'I've spent X on this show' stat."""
    if effective_min >= MIN_PER_YEAR:
        value = effective_min / MIN_PER_YEAR
        unit = "years"
    elif effective_min >= MIN_PER_MONTH:
        value = effective_min / MIN_PER_MONTH
        unit = "months"
    elif effective_min >= MIN_PER_WEEK:
        value = effective_min / MIN_PER_WEEK
        unit = "weeks"
    elif effective_min >= MIN_PER_DAY:
        value = effective_min / MIN_PER_DAY
        unit = "days"
    else:
        value = effective_min / MIN_PER_HOUR
        unit = "hours"
    # One decimal, dropping a trailing ".0".
    rendered = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{rendered} {unit}"


def compute(
    base_runtime_min: int,
    times_watched: int = 1,
    playback_speed: float = 1.0,
) -> WatchTime:
    """Compute a watch-time breakdown.

    times_watched multiplies the total (rewatch stat); playback_speed
    divides it (1.5x speed => 2/3 the time). Inputs are clamped to sane
    bounds so bad form data can't produce nonsense or divide-by-zero.
    """
    base = max(0, int(base_runtime_min or 0))
    times = max(1, int(times_watched or 1))
    speed = min(3.0, max(0.25, float(playback_speed or 1.0)))

    effective = round(base * times / speed)

    return WatchTime(
        base_runtime_min=base,
        times_watched=times,
        playback_speed=speed,
        effective_min=effective,
        hours=round(effective / MIN_PER_HOUR, 1),
        days=round(effective / MIN_PER_DAY, 1),
        weeks=round(effective / MIN_PER_WEEK, 1),
        breakdown=_humanize_duration(effective),
        share_stat=_share_stat(effective),
    )
