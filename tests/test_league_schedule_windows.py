# tests/test_league_schedule_windows.py
"""IANA schedule + DST rules for Lifecycle V1."""
from __future__ import annotations

from datetime import date, datetime, timezone

from leagues.schedule import assign_lifecycle_windows, local_resolution_instant, rebase_windows


def test_kathmandu_fixed_offset():
    # Asia/Kathmandu is UTC+5:45 year-round
    end = local_resolution_instant(date(2026, 7, 21), 20, "Asia/Kathmandu")
    assert end.tzinfo is not None
    assert end.astimezone(timezone.utc).hour == 14  # 20:00 +05:45 → 14:15 UTC
    assert end.astimezone(timezone.utc).minute == 15


def test_assign_fourteen_matchdays():
    windows = assign_lifecycle_windows(
        first_matchday_local_date=date(2026, 8, 1),
        timezone_name="Asia/Kathmandu",
        resolution_hour_local=20,
        matchday_count=14,
        season_open_utc=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )
    assert len(windows) == 14
    assert windows[0].matchday_number == 1
    assert windows[0].window_start < windows[0].window_end
    for i in range(1, 14):
        assert windows[i].window_start == windows[i - 1].window_end
        assert windows[i].window_end > windows[i].window_start


def test_new_york_spring_gap_uses_post_gap_time():
    # 2026-03-08 02:00 does not exist in America/New_York (spring forward)
    end = local_resolution_instant(date(2026, 3, 8), 2, "America/New_York")
    wall = end.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York"))
    # Should not land in the nonexistent 02:xx hour — typically 03:00 EDT
    assert wall.hour != 2 or wall.fold == 0
    assert (wall.hour, wall.minute) >= (3, 0) or wall.date() > date(2026, 3, 8)


def test_new_york_fall_overlap_uses_earlier_offset():
    # 2026-11-01 01:30 occurs twice; fold=0 → earlier (EDT)
    end = local_resolution_instant(date(2026, 11, 1), 1, "America/New_York")
    assert end.tzinfo is not None
    # Earlier offset is UTC-4 → 01:00 EDT = 05:00 UTC
    utc = end.astimezone(timezone.utc)
    assert utc.hour == 5


def test_rebase_windows_shifts_forward():
    windows = assign_lifecycle_windows(
        first_matchday_local_date=date(2026, 8, 1),
        timezone_name="UTC",
        resolution_hour_local=0,
        matchday_count=2,
    )
    shifted = rebase_windows(windows, 3600 * 48)
    assert shifted[0].window_end - windows[0].window_end == __import__("datetime").timedelta(days=2)
