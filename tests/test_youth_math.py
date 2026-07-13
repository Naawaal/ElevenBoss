# tests/test_youth_math.py
"""Academy growth math (015)."""
from __future__ import annotations

from player_engine.youth_math import (
    academy_daily_points,
    apply_academy_tick,
    is_promotion_ready,
    should_age_out,
    star_band,
)


def test_daily_points_monotonic_by_level() -> None:
    pot = 82
    assert academy_daily_points(5, pot) > academy_daily_points(1, pot)


def test_apply_tick_never_exceeds_potential() -> None:
    stats = {"pac": 60, "sho": 55, "pas": 50, "dri": 52, "def": 40, "phy": 58}
    # Force many OVR ups via high progress + high level
    r = apply_academy_tick(64, 66, 95, 5, stats, "FWD")
    assert r.overall <= 66
    for v in r.stats.values():
        assert v <= 66


def test_ready_at_65() -> None:
    assert is_promotion_ready(65) is True
    assert is_promotion_ready(64) is False


def test_age_out() -> None:
    assert should_age_out(20) is True
    assert should_age_out(19) is False


def test_star_band() -> None:
    assert star_band(74) == 1
    assert star_band(80) == 3
    assert star_band(90) == 5
