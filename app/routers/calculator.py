"""Watch-time calculator: standalone page + JSON API (single source of
truth for the math lives in services/calculator.py, per the all-Python goal)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Show
from ..services import calculator
from ..templating import templates

router = APIRouter()


class CalcRequest(BaseModel):
    base_runtime_min: int = Field(ge=0)
    times_watched: int = Field(default=1, ge=1, le=10_000)
    playback_speed: float = Field(default=1.0, ge=0.25, le=3.0)


@router.get("/calculator")
def calculator_page(
    request: Request,
    show: str | None = None,
    db: Session = Depends(get_db),
):
    """Standalone calculator: pick a show, its runtime auto-fills, then set a
    rewatch count + speed. ?show=<slug> selects a show directly."""
    prefill = None
    if show:
        prefill = db.execute(
            select(Show).where(Show.id == show)
        ).scalar_one_or_none()
    # (id, title) for the picker dropdown — only shows we can actually compute
    # a watch time for.
    shows = db.execute(
        select(Show.id, Show.title)
        .where(Show.total_runtime_min.isnot(None))
        .order_by(Show.title.asc())
    ).all()
    return templates.TemplateResponse(
        request,
        "calculator.html",
        {"title": "Watch-time calculator", "prefill": prefill, "shows": shows},
    )


@router.post("/api/calculate")
def calculate(payload: CalcRequest) -> dict:
    """Debounced client calls hit this; returns the full breakdown as JSON."""
    result = calculator.compute(
        base_runtime_min=payload.base_runtime_min,
        times_watched=payload.times_watched,
        playback_speed=payload.playback_speed,
    )
    return asdict(result)
