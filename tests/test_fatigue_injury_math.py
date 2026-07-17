# tests/test_fatigue_injury_math.py
"""Pure formula checks for fatigue + injury (A+C) — updated for 016 tier model."""
from __future__ import annotations

import random

import pytest

from player_engine.fatigue import (
    FATIGUE_BENCH_PER_MATCH,
    FATIGUE_RECOVERY_SESSION,
    apply_bench_rest,
    apply_passive_recovery,
    apply_recovery_session,
    apply_starter_drain,
    fatigue_stat_multiplier,
    match_fatigue_drain,
    passive_recovery_amount,
    recovery_batch_energy,
    recovery_session_eligible,
)
from player_engine.injury_math import (
    INJURY_ELIGIBLE_FATIGUE_BELOW,
    injury_chance,
    recovery_days_for_intensity,
    recovery_days_for_tier,
    roll_injury_tier,
    select_post_match_injury,
)


def test_drain_tier1_attack() -> None:
    # Tier 1, PHY 70, Attack → 8 - 7 + 4 = 5
    assert match_fatigue_drain(70, stance="attack", intensity_tier=1) == 5


def test_fatigue_penalties_and_no_energy_coupling() -> None:
    assert fatigue_stat_multiplier(100, "pac") == 1.0
    assert fatigue_stat_multiplier(60, "pac") == 0.92
    assert fatigue_stat_multiplier(30, "dri") == 0.85
    assert fatigue_stat_multiplier(10, "sho") == 0.75
    assert fatigue_stat_multiplier(0, "pas") == 0.70
    import player_engine.fatigue as mod

    src = open(mod.__file__, encoding="utf-8").read()
    assert "action_energy" not in src


def test_bench_and_passive_recovery_caps() -> None:
    assert FATIGUE_BENCH_PER_MATCH == 25
    assert apply_bench_rest(70) == 95
    assert apply_bench_rest(80) == 100
    assert apply_bench_rest(95) == 100
    assert apply_starter_drain(10, 25) == 0
    # Tier 1 defaults: 35 + TG×2
    assert passive_recovery_amount(1, intensity_tier=1) == 37
    assert passive_recovery_amount(3, intensity_tier=1) == 41
    assert passive_recovery_amount(5, intensity_tier=1) == 45
    assert apply_passive_recovery(90, intensity_tier=1) == 100
    assert apply_passive_recovery(0, tg_level=5, intensity_tier=1) == 45
    assert apply_passive_recovery(50, in_hospital=True, tg_level=5) == 95
    assert apply_recovery_session(50) == 50 + FATIGUE_RECOVERY_SESSION
    assert apply_recovery_session(70) == 100


def test_recovery_session_eligible_gates() -> None:
    assert recovery_session_eligible({"fatigue": 50}) is True
    assert recovery_session_eligible({"fatigue": 99}) is True
    assert recovery_session_eligible({"fatigue": 100}) is False
    assert recovery_session_eligible({"fatigue": 40, "injury_tier": 1}) is False
    assert recovery_session_eligible({"fatigue": 40, "in_hospital": True}) is False
    assert recovery_session_eligible({"fatigue": 40, "injury_tier": None, "in_hospital": False}) is True


def test_recovery_batch_energy_scaling() -> None:
    assert recovery_batch_energy(1) == 5
    assert recovery_batch_energy(3) == 15
    assert recovery_batch_energy(2, per_player=7) == 14
    with pytest.raises(ValueError):
        recovery_batch_energy(0)
    with pytest.raises(ValueError):
        recovery_batch_energy(4)


def test_injury_chance_and_tier_100_is_major() -> None:
    assert abs(injury_chance(100, 22, 70, intensity_tier=1) - 0.0025) < 1e-9

    class _R:
        def randint(self, a: int, b: int) -> int:
            return 100

    assert roll_injury_tier(_R()) == 3


def test_ac_soft_cap_skips_fresh_and_max_one() -> None:
    rng = random.Random(0)
    fresh = [
        {"id": "a", "fatigue": 90, "age": 33, "phy": 50},
        {"id": "b", "fatigue": 80, "age": 36, "phy": 40},
    ]
    assert select_post_match_injury(fresh, rng=rng) is None

    class AlwaysHit:
        def random(self) -> float:
            return 0.0

        def randint(self, a: int, b: int) -> int:
            return 50

    starters = [
        {"id": "fresh", "fatigue": 90, "age": 22, "phy": 80},
        {"id": "tired1", "fatigue": 50, "age": 28, "phy": 70},
        {"id": "tired2", "fatigue": 40, "age": 30, "phy": 60},
    ]
    hit = select_post_match_injury(starters, rng=AlwaysHit())
    assert hit is not None
    assert hit.player_card_id == "tired1"
    assert hit.tier == 1
    assert starters[0]["fatigue"] >= INJURY_ELIGIBLE_FATIGUE_BELOW


def test_hospital_recovery_days() -> None:
    # Moderate Tier1 @ H3 → 3/1.6 = 1.875 → 2
    assert recovery_days_for_intensity(2, 1, 3) == 2
    assert recovery_days_for_tier(2, 3, intensity_tier=1) == 2
    assert recovery_days_for_intensity(1, 1, 0) == 1  # Minor 0.99 → 1
    assert recovery_days_for_intensity(3, 1, 0) == 8  # Major T1 untreated
