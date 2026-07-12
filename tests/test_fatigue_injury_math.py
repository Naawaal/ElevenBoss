# tests/test_fatigue_injury_math.py
"""Pure formula checks for fatigue + injury (A+C)."""
from __future__ import annotations

import random

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
)
from player_engine.injury_math import (
    INJURY_ELIGIBLE_FATIGUE_BELOW,
    injury_chance,
    recovery_days_for_tier,
    roll_injury_tier,
    select_post_match_injury,
)


def test_drain_gdd_example() -> None:
    # PHY 70, Attack, intensity → 18 - 10.5 + 8 + 5 = 20.5 → 21
    assert match_fatigue_drain(70, stance="attack", intensity=True) == 21


def test_fatigue_penalties_and_no_energy_coupling() -> None:
    assert fatigue_stat_multiplier(100, "pac") == 1.0
    assert fatigue_stat_multiplier(60, "pac") == 0.92
    assert fatigue_stat_multiplier(30, "dri") == 0.85
    assert fatigue_stat_multiplier(10, "sho") == 0.75
    assert fatigue_stat_multiplier(0, "pas") == 0.70
    # Helpers must not mention action_energy (import-level sanity)
    import player_engine.fatigue as mod

    src = open(mod.__file__, encoding="utf-8").read()
    assert "action_energy" not in src


def test_bench_and_passive_recovery_caps() -> None:
    assert FATIGUE_BENCH_PER_MATCH == 25
    assert apply_bench_rest(70) == 95
    assert apply_bench_rest(80) == 100  # 80+25 clamps
    assert apply_bench_rest(95) == 100
    assert apply_starter_drain(10, 25) == 0
    assert passive_recovery_amount(1) == 30
    assert passive_recovery_amount(3) == 40
    assert passive_recovery_amount(5) == 50
    assert apply_passive_recovery(90) == 100  # TG1 default +30
    assert apply_passive_recovery(0, tg_level=5) == 50
    assert apply_passive_recovery(50, in_hospital=True, tg_level=5) == 95  # hospital ignores TG
    assert apply_recovery_session(50) == 50 + FATIGUE_RECOVERY_SESSION
    assert apply_recovery_session(70) == 100


def test_injury_chance_and_tier_100_is_major() -> None:
    assert injury_chance(100, 22, 70) == 0.004
    # Force tier roll 100 via seeded rng that always returns 100 for randint
    class _R:
        def randint(self, a: int, b: int) -> int:
            return 100

    assert roll_injury_tier(_R()) == 3  # Major, not career-ending


def test_ac_soft_cap_skips_fresh_and_max_one() -> None:
    rng = random.Random(0)
    fresh = [
        {"id": "a", "fatigue": 90, "age": 33, "phy": 50},
        {"id": "b", "fatigue": 80, "age": 36, "phy": 40},
    ]
    assert select_post_match_injury(fresh, rng=rng) is None

    # Force hit on first eligible: fatigue 50, high chance path with rng that always hits
    class AlwaysHit:
        def random(self) -> float:
            return 0.0

        def randint(self, a: int, b: int) -> int:
            return 50  # Minor

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
    # Moderate 4 days at hospital L3 → 4/1.6 = 2.5 → 3
    assert recovery_days_for_tier(2, 3) == 3
    assert recovery_days_for_tier(1, 0) == 1
    assert recovery_days_for_tier(3, 0) == 7
