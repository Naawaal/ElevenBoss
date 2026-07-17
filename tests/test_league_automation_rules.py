# tests/test_league_automation_rules.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from leagues.automation import (
    automation_effective,
    can_open_auto_registration,
    evaluate_registration_close,
    next_monday_0005_utc,
    registration_closes_at,
)


def test_next_monday_before_slot_same_monday() -> None:
    # Monday 2026-07-13 00:00 UTC — before 00:05 → same Monday 00:05
    now = datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)
    assert now.weekday() == 0
    assert next_monday_0005_utc(now) == datetime(2026, 7, 13, 0, 5, tzinfo=timezone.utc)


def test_next_monday_after_slot_skips_week() -> None:
    now = datetime(2026, 7, 13, 0, 6, tzinfo=timezone.utc)
    assert next_monday_0005_utc(now) == datetime(2026, 7, 20, 0, 5, tzinfo=timezone.utc)


def test_next_monday_from_wednesday() -> None:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)  # Wed
    assert next_monday_0005_utc(now) == datetime(2026, 7, 20, 0, 5, tzinfo=timezone.utc)


def test_registration_closes_48h() -> None:
    opened = datetime(2026, 7, 15, 0, 5, tzinfo=timezone.utc)
    assert registration_closes_at(opened, 48) == opened + timedelta(hours=48)


def test_evaluate_registration_close() -> None:
    assert evaluate_registration_close(2, 2) == "start"
    assert evaluate_registration_close(1, 2) == "fail_under_min"


def test_can_open_respects_next_at() -> None:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    next_at = datetime(2026, 7, 20, 0, 5, tzinfo=timezone.utc)
    assert can_open_auto_registration(now, next_at, False) is False
    assert can_open_auto_registration(next_at, next_at, False) is True
    assert can_open_auto_registration(now, None, True) is False


def test_force_end_style_monday_gate_blocks_same_day_reopen() -> None:
    """E10: after Force End schedules next Monday, Phase C must not open early."""
    wednesday = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    next_at = next_monday_0005_utc(wednesday)
    assert can_open_auto_registration(wednesday, next_at, has_active_or_reg=False) is False
    assert can_open_auto_registration(next_at, next_at, has_active_or_reg=False) is True


def test_automation_effective_truth() -> None:
    assert automation_effective(False, None) is False
    assert automation_effective(True, None) is True
    assert automation_effective(True, True) is True
    assert automation_effective(True, False) is False
    assert automation_effective(False, True) is False
