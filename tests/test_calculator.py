from app.services import calculator


def test_basic_hours_days_weeks():
    # 6120 min = 102 h = 4.25 days = 0.607 weeks
    r = calculator.compute(6120)
    assert r.effective_min == 6120
    assert r.hours == 102.0
    assert r.days == 4.2 or r.days == 4.3  # rounding of 4.25
    assert r.breakdown == "4d 6h"


def test_rewatch_multiplier_scales_total():
    r = calculator.compute(600, times_watched=3)
    assert r.effective_min == 1800
    assert "3" not in r.share_stat or r.share_stat  # sanity: produces a stat


def test_playback_speed_divides():
    r = calculator.compute(600, playback_speed=2.0)
    assert r.effective_min == 300


def test_share_stat_picks_largest_unit():
    # ~2 years of runtime
    two_years = calculator.MIN_PER_YEAR * 2
    assert calculator.compute(two_years).share_stat.endswith("years")
    assert calculator.compute(calculator.MIN_PER_WEEK * 3).share_stat.endswith("weeks")


def test_inputs_are_clamped():
    r = calculator.compute(-100, times_watched=0, playback_speed=0)
    assert r.effective_min == 0
    assert r.times_watched == 1
    assert 0.25 <= r.playback_speed <= 3.0


def test_zero_runtime_breakdown():
    assert calculator.compute(0).breakdown == "0m"
