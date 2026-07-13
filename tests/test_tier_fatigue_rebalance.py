# tests/test_tier_fatigue_rebalance.py
"""016 division-tier fatigue / injury rebalance pure math."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from player_engine.fatigue import (
    TIER_DRAIN_BASE,
    count_heavily_fatigued,
    match_fatigue_drain,
    passive_recovery_amount,
)
from player_engine.injury_math import (
    TIER_INJURY_BASE,
    fair_hospital_final_eta,
    fair_overflow_remaining_days,
    injury_chance,
    recovery_days_for_intensity,
    should_early_discharge,
    untreated_base_days,
)
from player_engine.intensity import intensity_tier_for_division


def test_division_intensity_map_222() -> None:
    assert intensity_tier_for_division("Grassroots") == 1
    assert intensity_tier_for_division("Amateur") == 1
    assert intensity_tier_for_division("Semi-Pro") == 2
    assert intensity_tier_for_division("Professional") == 2
    assert intensity_tier_for_division("Elite") == 3
    assert intensity_tier_for_division("Legendary") == 3
    assert intensity_tier_for_division(None) == 1
    assert intensity_tier_for_division("Unknown") == 1


def test_us1_tier1_drain_and_passive() -> None:
    assert TIER_DRAIN_BASE[1] == 8
    assert match_fatigue_drain(70, stance="neutral", intensity_tier=1) == 1
    assert match_fatigue_drain(70, stance="attack", intensity_tier=1) == 5
    assert match_fatigue_drain(70, stance="defend", intensity_tier=1) == 0
    assert passive_recovery_amount(3, intensity_tier=1) == 41


def test_us2_tier3_anchors() -> None:
    assert TIER_DRAIN_BASE[3] == 16
    assert passive_recovery_amount(3, intensity_tier=3) == 21
    assert recovery_days_for_intensity(2, 3, 5) == 4  # Moderate @ T3 H5
    assert recovery_days_for_intensity(3, 3, 0) == 20  # Major untreated
    assert abs(injury_chance(100, 22, 70, intensity_tier=3) - 0.006) < 1e-9


def test_us3_tier2_and_drain_order() -> None:
    assert TIER_DRAIN_BASE[2] == 12
    assert passive_recovery_amount(0, intensity_tier=2) == 25
    assert abs(TIER_INJURY_BASE[2] - 0.004) < 1e-9
    assert untreated_base_days(2, 2) == 5.0
    assert TIER_DRAIN_BASE[1] < TIER_DRAIN_BASE[2] < TIER_DRAIN_BASE[3]


def test_fair_eta_never_lengthens() -> None:
    admission = datetime(2026, 7, 1, tzinfo=timezone.utc)
    old_eta = admission + timedelta(days=20)
    final = fair_hospital_final_eta(
        admission=admission,
        current_eta=old_eta,
        tier=2,
        hospital_level=5,
        intensity_tier=3,
    )
    assert final == admission + timedelta(days=4)
    assert final <= old_eta
    assert should_early_discharge(
        now=admission + timedelta(days=5),
        final_eta=final,
    )


def test_fair_overflow_and_fatigue_warning_count() -> None:
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    remain = fair_overflow_remaining_days(
        tier=2,
        injury_started_at=now - timedelta(days=3),
        current_remaining=8,
        now=now,
        intensity_tier=3,
    )
    # untreated Moderate T3 = 8; elapsed 3 → remain 5; min(8,5)=5
    assert remain == 5
    starters = [
        {"fatigue": 20},
        {"fatigue": 40},
        {"fatigue": 10},
        {"fatigue": 90},
    ]
    assert count_heavily_fatigued(starters) == 2
