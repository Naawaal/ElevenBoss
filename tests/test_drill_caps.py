# tests/test_drill_caps.py
"""Effective club daily drill count (soft-reset display)."""
from __future__ import annotations

from datetime import date, timedelta

from player_engine.drill_caps import effective_daily_drill_count


def test_effective_count_resets_when_stale_or_null() -> None:
    today = date(2026, 7, 12)
    assert effective_daily_drill_count(20, today - timedelta(days=1), today=today) == 0
    assert effective_daily_drill_count(20, None, today=today) == 0


def test_effective_count_keeps_today() -> None:
    today = date(2026, 7, 12)
    assert effective_daily_drill_count(6, today, today=today) == 6
    assert effective_daily_drill_count(-1, today, today=today) == 0
