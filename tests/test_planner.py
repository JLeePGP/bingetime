from datetime import date

from app.services import planner


def test_finish_date_from_hours_per_week():
    # 1200 min = 20 h; at 10 h/week -> 2 weeks -> 14 days
    p = planner.build_plan(1200, 10, start=date(2026, 1, 1))
    assert p.weeks_needed == 2.0
    assert p.days_needed == 14
    assert p.finish_date == date(2026, 1, 15)


def test_partial_week_rounds_up_days():
    # 630 min = 10.5 h; at 10 h/week -> 1.05 weeks -> ceil(7.35) = 8 days
    p = planner.build_plan(630, 10, start=date(2026, 1, 1))
    assert p.days_needed == 8


def test_ics_has_required_fields():
    p = planner.build_plan(1200, 10, start=date(2026, 1, 1))
    ics = planner.build_ics("One Piece", p, start=date(2026, 1, 1))
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "DTSTART;VALUE=DATE:20260115" in ics
    assert "SUMMARY:Finish binging One Piece" in ics
    assert ics.endswith("\r\n")


def test_bad_input_is_clamped():
    p = planner.build_plan(0, 0)
    assert p.total_runtime_min == 0
    assert p.hours_per_week >= 0.5
