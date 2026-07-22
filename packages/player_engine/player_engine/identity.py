# packages/player_engine/player_engine/identity.py
"""US-42.1 soft identity lifecycle thresholds (pure)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

IdentityStatus = Literal["active", "inactive", "abandoned"]

INACTIVE_DAYS = 30
ABANDONED_DAYS = 90


def classify_status(
    last_activity: datetime,
    now: datetime | None = None,
    *,
    inactive_days: int = INACTIVE_DAYS,
    abandoned_days: int = ABANDONED_DAYS,
) -> IdentityStatus:
    """Return identity status from last qualifying activity timestamp."""
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    days = (ref - last_activity).total_seconds() / 86400.0
    if days >= abandoned_days:
        return "abandoned"
    if days >= inactive_days:
        return "inactive"
    return "active"


def days_since_activity(last_activity: datetime, now: datetime | None = None) -> float:
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return (ref - last_activity).total_seconds() / 86400.0
