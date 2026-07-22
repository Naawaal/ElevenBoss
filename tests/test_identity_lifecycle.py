"""US-42.1 soft identity lifecycle pure math."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from player_engine.identity import (
    ABANDONED_DAYS,
    INACTIVE_DAYS,
    classify_status,
    days_since_activity,
)


def test_thresholds_defaults():
    assert INACTIVE_DAYS == 30
    assert ABANDONED_DAYS == 90


def test_classify_active_under_30_days():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    last = now - timedelta(days=29)
    assert classify_status(last, now) == "active"


def test_classify_inactive_at_30_days():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    last = now - timedelta(days=30)
    assert classify_status(last, now) == "inactive"


def test_classify_abandoned_at_90_days():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    last = now - timedelta(days=90)
    assert classify_status(last, now) == "abandoned"


def test_days_since_activity():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    last = now - timedelta(days=2)
    assert abs(days_since_activity(last, now) - 2.0) < 1e-6
