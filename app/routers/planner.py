"""Binge planner: standalone page + JSON API + .ics calendar export."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Show
from ..services import planner
from ..templating import templates

router = APIRouter()


class PlanRequest(BaseModel):
    total_runtime_min: int = Field(ge=0)
    hours_per_week: float = Field(gt=0, le=168)


@router.get("/planner")
def planner_page(
    request: Request,
    show: str | None = None,
    db: Session = Depends(get_db),
):
    prefill = None
    if show:
        prefill = db.execute(
            select(Show).where(Show.id == show)
        ).scalar_one_or_none()
    return templates.TemplateResponse(
        request,
        "planner.html",
        {"title": "Binge planner", "prefill": prefill},
    )


@router.post("/api/plan")
def make_plan(payload: PlanRequest) -> dict:
    plan = planner.build_plan(
        total_runtime_min=payload.total_runtime_min,
        hours_per_week=payload.hours_per_week,
    )
    return {
        "total_runtime_min": plan.total_runtime_min,
        "hours_per_week": plan.hours_per_week,
        "weeks_needed": plan.weeks_needed,
        "days_needed": plan.days_needed,
        "finish_date": plan.finish_date.isoformat(),
    }


@router.get("/planner/export.ics")
def export_ics(
    title: str = Query(default="your show"),
    total_runtime_min: int = Query(ge=0),
    hours_per_week: float = Query(gt=0, le=168),
):
    """Download a calendar event marking the finish-by date."""
    start = date.today()
    plan = planner.build_plan(total_runtime_min, hours_per_week, start=start)
    ics = planner.build_ics(title, plan, start=start)
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "binge"
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="bingetime-{safe}.ics"'
        },
    )
