# tests/test_league_dynamics_windows.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from leagues.dynamics_windows import assign_dynamics_windows, utc_day_floor


def test_utc_day_floor() -> None:
    start = datetime(2026, 7, 15, 15, 30, tzinfo=timezone.utc)
    assert utc_day_floor(start) == datetime(2026, 7, 15, tzinfo=timezone.utc)


def test_midday_start_md1_ends_next_midnight() -> None:
    start = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)
    windows = assign_dynamics_windows(start, 14)
    assert len(windows) == 14
    assert windows[0]["matchday"] == 1
    assert windows[0]["window_start"] == start
    assert windows[0]["window_end"] == datetime(2026, 7, 16, tzinfo=timezone.utc)
    assert windows[1]["window_start"] == datetime(2026, 7, 16, tzinfo=timezone.utc)
    assert windows[1]["window_end"] == datetime(2026, 7, 17, tzinfo=timezone.utc)
    assert windows[13]["window_end"] == datetime(2026, 7, 15, tzinfo=timezone.utc) + timedelta(days=14)


def test_naive_datetime_treated_as_utc() -> None:
    start = datetime(2026, 7, 15, 12, 0)  # naive
    windows = assign_dynamics_windows(start, 1)
    assert windows[0]["window_end"].tzinfo == timezone.utc
