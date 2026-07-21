# packages/leagues/leagues/schedule.py
"""Guild IANA timezone + local hour → precomputed UTC matchday windows (026 Q1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MatchdayUtcWindow:
    matchday_number: int
    window_start: datetime
    window_end: datetime


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local_resolution_instant(
    local_day: date,
    hour: int,
    tz_name: str,
) -> datetime:
    """
    Build the local resolution instant for ``local_day`` at ``hour:00``.

    DST rules (research D2 / FR-006):
    - Gap (spring forward): use the first valid local time after the gap.
    - Overlap (fall back): use the earlier (DST) offset occurrence.
    """
    if hour < 0 or hour > 23:
        raise ValueError("hour must be 0–23")
    tz = ZoneInfo(tz_name)
    # Fold=0 → earlier offset on overlap; fold=1 → later.
    naive = datetime(local_day.year, local_day.month, local_day.day, hour, 0, 0)
    try:
        aware = naive.replace(tzinfo=tz, fold=0)
        # Detect nonexistent time: round-trip through UTC and compare wall clock.
        wall = aware.astimezone(tz).replace(tzinfo=None)
        if wall != naive:
            # Gap: walk forward in 15-minute steps until wall matches intent hour/day
            # or we land on first valid time after gap with same or later clock.
            probe = naive
            for _ in range(8):
                probe = probe + timedelta(minutes=15)
                cand = probe.replace(tzinfo=tz, fold=0)
                wall2 = cand.astimezone(tz).replace(tzinfo=None)
                if wall2.date() == local_day and wall2.hour >= hour:
                    return _as_utc(cand)
                if wall2.date() > local_day:
                    return _as_utc(cand)
            return _as_utc(aware)
        return _as_utc(aware)
    except Exception:
        # zoneinfo rarely raises; keep deterministic fallback
        return _as_utc(naive.replace(tzinfo=tz, fold=0))


def assign_lifecycle_windows(
    *,
    first_matchday_local_date: date,
    timezone_name: str,
    resolution_hour_local: int,
    matchday_count: int = 14,
    season_open_utc: datetime | None = None,
) -> list[MatchdayUtcWindow]:
    """
    Precompute UTC windows for matchdays 1..N.

    ``window_end`` = local resolution instant on that matchday's calendar date.
    ``window_start`` = previous matchday ``window_end``, or ``season_open_utc`` for MD1.
    """
    if matchday_count < 1:
        raise ValueError("matchday_count must be >= 1")
    ends: list[datetime] = []
    for n in range(matchday_count):
        day = first_matchday_local_date + timedelta(days=n)
        ends.append(local_resolution_instant(day, resolution_hour_local, timezone_name))

    open0 = _as_utc(season_open_utc) if season_open_utc else ends[0] - timedelta(hours=24)
    windows: list[MatchdayUtcWindow] = []
    for i, end in enumerate(ends):
        start = open0 if i == 0 else ends[i - 1]
        if start >= end:
            # Ensure positive window if open was late — clamp start to end - 1h
            start = end - timedelta(hours=1)
        windows.append(MatchdayUtcWindow(matchday_number=i + 1, window_start=start, window_end=end))
    return windows


def rebase_windows(
    windows: list[MatchdayUtcWindow],
    pause_seconds: int,
) -> list[MatchdayUtcWindow]:
    """Shift unresolved-style windows forward by pause duration (pure helper)."""
    if pause_seconds <= 0:
        return list(windows)
    delta = timedelta(seconds=pause_seconds)
    return [
        MatchdayUtcWindow(
            matchday_number=w.matchday_number,
            window_start=_as_utc(w.window_start) + delta,
            window_end=_as_utc(w.window_end) + delta,
        )
        for w in windows
    ]
