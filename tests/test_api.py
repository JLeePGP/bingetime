"""Endpoint smoke tests that don't require a database connection."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_calculate_api():
    resp = client.post(
        "/api/calculate",
        json={"base_runtime_min": 6120, "times_watched": 1, "playback_speed": 1.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hours"] == 102.0
    assert body["breakdown"] == "4d 6h"


def test_calculate_api_validates():
    resp = client.post("/api/calculate", json={"base_runtime_min": -5})
    assert resp.status_code == 422


def test_plan_api():
    resp = client.post(
        "/api/plan", json={"total_runtime_min": 1200, "hours_per_week": 10}
    )
    assert resp.status_code == 200
    assert resp.json()["days_needed"] == 14


def test_ics_export():
    resp = client.get(
        "/planner/export.ics",
        params={"title": "One Piece", "total_runtime_min": 1200, "hours_per_week": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in resp.text


def test_calculator_page_renders_without_db():
    # No ?show param => no DB query => template renders standalone.
    resp = client.get("/calculator")
    assert resp.status_code == 200
    assert "Watch-time calculator" in resp.text
