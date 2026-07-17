# packages/leagues/leagues/automation.py
"""Pure rules for autonomous league registration windows (021)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def next_monday_0005_utc(now: datetime) -> datetime:
    """Next Monday 00:05 UTC strictly after ``now`` when already past this week's slot."""
    now = _as_utc(now)
    # Monday=0 … Sunday=6
    days_until_mon = (0 - now.weekday()) % 7
    candidate = datetime(now.year, now.month, now.day, 0, 5, tzinfo=timezone.utc) + timedelta(
        days=days_until_mon
    )
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def registration_closes_at(opened_at: datetime, hours: int = 48) -> datetime:
    return _as_utc(opened_at) + timedelta(hours=int(hours))


def can_open_auto_registration(
    now: datetime,
    next_at: datetime | None,
    has_active_or_reg: bool,
) -> bool:
    if has_active_or_reg:
        return False
    now = _as_utc(now)
    if next_at is not None and now < _as_utc(next_at):
        return False
    return True


def evaluate_registration_close(
    human_count: int,
    min_humans: int,
) -> Literal["start", "fail_under_min"]:
    if int(human_count) >= int(min_humans):
        return "start"
    return "fail_under_min"


def automation_effective(
    global_enabled: bool,
    guild_flag: bool | None,
) -> bool:
    """Global on AND (guild NULL inherit OR guild true)."""
    if not global_enabled:
        return False
    if guild_flag is None:
        return True
    return bool(guild_flag)
