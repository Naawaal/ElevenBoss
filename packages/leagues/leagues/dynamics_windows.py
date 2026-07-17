# packages/leagues/leagues/dynamics_windows.py
"""UTC midnight matchday windows for League Dynamics seasons."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict


class MatchdayWindow(TypedDict):
    matchday: int
    window_start: datetime
    window_end: datetime


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_day_floor(dt: datetime) -> datetime:
    """00:00:00 UTC of the calendar day containing ``dt``."""
    u = _as_utc(dt)
    return datetime(u.year, u.month, u.day, tzinfo=timezone.utc)


def assign_dynamics_windows(
    start_time: datetime,
    total_matchdays: int,
) -> list[MatchdayWindow]:
    """
    Assign hard-close windows for Dynamics seasons (D4).

    For matchday N: window_end = utc_day_floor(start) + N days (00:00 UTC).
    window_start = start_time for N=1, else previous midnight end.
    """
    if total_matchdays < 1:
        raise ValueError("total_matchdays must be >= 1")
    start = _as_utc(start_time)
    day0 = utc_day_floor(start)
    out: list[MatchdayWindow] = []
    for n in range(1, total_matchdays + 1):
        window_end = day0 + timedelta(days=n)
        window_start = start if n == 1 else day0 + timedelta(days=n - 1)
        out.append(
            {
                "matchday": n,
                "window_start": window_start,
                "window_end": window_end,
            }
        )
    return out
