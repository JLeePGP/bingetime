"""Binge planner — finish-by date from available hours/week, plus .ics export."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil


@dataclass(frozen=True)
class Plan:
    total_runtime_min: int
    hours_per_week: float
    weeks_needed: float
    days_needed: int
    finish_date: date


def build_plan(
    total_runtime_min: int,
    hours_per_week: float,
    start: date | None = None,
) -> Plan:
    """Days until finish = ceil(total / daily budget), where the weekly
    budget is spread evenly across 7 days. Clamped against bad input."""
    total = max(0, int(total_runtime_min or 0))
    hpw = max(0.5, float(hours_per_week or 0))
    start = start or date.today()

    minutes_per_week = hpw * 60
    weeks_needed = total / minutes_per_week if minutes_per_week else 0.0
    days_needed = ceil(weeks_needed * 7)
    finish = start + timedelta(days=days_needed)

    return Plan(
        total_runtime_min=total,
        hours_per_week=hpw,
        weeks_needed=round(weeks_needed, 1),
        days_needed=days_needed,
        finish_date=finish,
    )


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_ics(
    show_title: str,
    plan: Plan,
    start: date | None = None,
) -> str:
    """A single all-day VEVENT marking the finish-by date.

    Uses CRLF line endings and a floating all-day date per RFC 5545.
    """
    start = start or date.today()
    finish = plan.finish_date
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = f"{uuid.uuid4()}@bingetime.tv"

    summary = _ics_escape(f"Finish binging {show_title}")
    desc = _ics_escape(
        f"BingeTime plan: {plan.hours_per_week:g} hrs/week starting "
        f"{start.isoformat()} finishes {finish.isoformat()} "
        f"(~{plan.weeks_needed:g} weeks)."
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BingeTime.tv//Binge Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{finish.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(finish + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{desc}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
