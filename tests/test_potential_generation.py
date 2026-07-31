# tests/test_potential_generation.py
from __future__ import annotations

import random

import pytest

from player_engine import (
    RARITY_POT_CAPS,
    apply_dynamic_potential_boost,
    generate_potential,
    potential_tier_label,
)


def test_young_legendary_high_ceiling() -> None:
    rng = random.Random(42)
    pot = generate_potential(88, 17, "Legendary", "FWD", rng=rng)
    assert pot >= 88
    assert pot <= RARITY_POT_CAPS["Legendary"]


def test_veteran_common_near_ovr() -> None:
    rng = random.Random(99)
    pot = generate_potential(62, 35, "Common", "DEF", rng=rng)
    assert pot >= 62
    assert pot <= RARITY_POT_CAPS["Common"]
    assert pot <= 68


def test_potential_never_below_ovr() -> None:
    rng = random.Random(7)
    for _ in range(50):
        ovr = rng.randint(50, 85)
        pot = generate_potential(ovr, 28, "Rare", "MID", rng=rng)
        assert pot >= ovr


def test_distribution_has_variety() -> None:
    rng = random.Random(123)
    pots = [
        generate_potential(
            rng.randint(50, 70),
            rng.randint(18, 34),
            rng.choice(["Common", "Rare", "Epic"]),
            "MID",
            rng=rng,
        )
        for _ in range(100)
    ]
    assert len(set(pots)) > 20
    assert min(pots) >= 40
    assert max(pots) <= 92
    mid_band = sum(1 for p in pots if 60 <= p <= 85)
    assert mid_band >= 40


def test_rarity_caps_respected() -> None:
    rng = random.Random(0)
    for rarity, cap in RARITY_POT_CAPS.items():
        for _ in range(30):
            ovr = min(70, cap)
            pot = generate_potential(ovr, 18, rarity, "FWD", rng=rng)
            assert pot <= cap


def test_generate_rejects_ovr_above_cap() -> None:
    with pytest.raises(ValueError, match="maximum is 75"):
        generate_potential(76, 18, "Common", "MID", rng=random.Random(1))
    with pytest.raises(ValueError, match="maximum is 85"):
        generate_potential(86, 18, "Rare", "MID", rng=random.Random(1))
    with pytest.raises(ValueError, match="maximum is 92"):
        generate_potential(93, 18, "Epic", "MID", rng=random.Random(1))


def test_dynamic_boost_respects_rarity() -> None:
    assert apply_dynamic_potential_boost(80, 78, 5, "Rare") == 85
    assert apply_dynamic_potential_boost(82, 78, 10, "Rare") == 85
    assert apply_dynamic_potential_boost(92, 90, 5, "Epic") == 92
    assert apply_dynamic_potential_boost(74, 70, 5, "Common") == 75
    assert apply_dynamic_potential_boost(97, 95, 5, "Legendary") == 99


def test_potential_tier_labels() -> None:
    assert potential_tier_label(92) == "World Class"
    assert potential_tier_label(86) == "High Potential"
    assert potential_tier_label(60) == "Limited"
