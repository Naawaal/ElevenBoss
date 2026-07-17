# tests/test_injury_eta_backfill.py
"""Pure fair-recalc helpers for 012 hospital ETA backfill (016 intensity anchors)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from player_engine.injury_math import (
    fair_hospital_candidate_eta,
    fair_hospital_final_eta,
    fair_overflow_remaining_days,
    new_total_recovery_days,
    should_early_discharge,
    untreated_base_days,
)


def test_new_total_major_h0_is_8() -> None:
    # Major @ Tier1 H0: Moderate_base(3) × 2.5 = 7.5 → ceil 8 (016)
    assert new_total_recovery_days(3, 0) == 8
    assert new_total_recovery_days(1, 0) == 1
    # Moderate @ H3: 3 / (1 + 0.6) = 1.875 → ceil 2
    assert new_total_recovery_days(2, 3) == 2


def test_fair_hospital_shortens_never_lengthens() -> None:
    admission = datetime(2026, 7, 1, tzinfo=timezone.utc)
    far = admission + timedelta(days=20)
    final = fair_hospital_final_eta(
        admission=admission,
        current_eta=far,
        tier=3,
        hospital_level=0,
    )
    assert final == admission + timedelta(days=8)

    already_short = admission + timedelta(days=3)
    kept = fair_hospital_final_eta(
        admission=admission,
        current_eta=already_short,
        tier=3,
        hospital_level=0,
    )
    assert kept == already_short


def test_candidate_anchored_idempotent() -> None:
    admission = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    # Moderate untreated @ Tier1 = 3 days
    c1 = fair_hospital_candidate_eta(admission=admission, tier=2, hospital_level=0)
    c2 = fair_hospital_candidate_eta(admission=admission, tier=2, hospital_level=0)
    assert c1 == c2 == admission + timedelta(days=3)
    final = fair_hospital_final_eta(
        admission=admission, current_eta=c1, tier=2, hospital_level=0
    )
    assert final == c1


def test_early_discharge_gate() -> None:
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    assert should_early_discharge(now=now, final_eta=now) is True
    assert should_early_discharge(now=now, final_eta=now - timedelta(hours=1)) is True
    assert should_early_discharge(now=now, final_eta=now + timedelta(hours=1)) is False


def test_overflow_remaining_credits_elapsed() -> None:
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    started = now - timedelta(days=6)
    # Major untreated base 7.5; 6 elapsed → ceil(1.5)=2 left; never above current 14
    assert untreated_base_days(3, 1) == 7.5
    assert (
        fair_overflow_remaining_days(
            tier=3,
            injury_started_at=started,
            current_remaining=14,
            now=now,
        )
        == 2
    )
    assert (
        fair_overflow_remaining_days(
            tier=3,
            injury_started_at=started,
            current_remaining=0,
            now=now,
        )
        == 0
    )
    assert (
        fair_overflow_remaining_days(
            tier=3,
            injury_started_at=now - timedelta(days=8),
            current_remaining=5,
            now=now,
        )
        == 0
    )
    # Minor untreated ~0.99 → ceil remain 1 when elapsed 0
    assert (
        fair_overflow_remaining_days(
            tier=1,
            injury_started_at=None,
            current_remaining=3,
            now=now,
        )
        == 1
    )
