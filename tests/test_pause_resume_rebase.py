# tests/test_pause_resume_rebase.py
from __future__ import annotations

from datetime import date, timedelta

from leagues.schedule import assign_lifecycle_windows, rebase_windows


def test_pause_two_days_shifts_all_windows():
    windows = assign_lifecycle_windows(
        first_matchday_local_date=date(2026, 9, 1),
        timezone_name="UTC",
        resolution_hour_local=12,
        matchday_count=3,
    )
    shifted = rebase_windows(windows, int(timedelta(days=2).total_seconds()))
    for a, b in zip(windows, shifted):
        assert b.window_start - a.window_start == timedelta(days=2)
        assert b.window_end - a.window_end == timedelta(days=2)
        assert b.matchday_number == a.matchday_number
