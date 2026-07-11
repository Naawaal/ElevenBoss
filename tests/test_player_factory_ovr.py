"""Deterministic True OVR balancing for create_player_card."""
from __future__ import annotations

import random

from player_engine import create_player_card
from player_engine.engine import calculate_true_ovr


def test_batch_overall_matches_target() -> None:
    r = random.Random(7)
    positions = ["GK", "DEF", "MID", "FWD"]
    rarities = ["Common", "Rare", "Epic", "Legendary"]
    ranges = {
        "Common": (50, 64),
        "Rare": (65, 74),
        "Epic": (75, 84),
        "Legendary": (85, 94),  # leave headroom under potential ceiling
    }
    misses = 0
    for i in range(200):
        pos = positions[i % 4]
        rarity = rarities[i % 4]
        lo, hi = ranges[rarity]
        target = r.randint(lo, hi)
        card = create_player_card(
            position=pos,
            rarity=rarity,
            target_ovr=target,
            first_name="A",
            last_name="B",
            age=22,
            rng=r,
        )
        recomputed = calculate_true_ovr(
            card.position,
            {
                "pac": card.pac,
                "sho": card.sho,
                "pas": card.pas,
                "dri": card.dri,
                "def": card.def_stat,
                "phy": card.phy,
            },
            [],
            card.potential,
        )
        assert card.overall == recomputed
        assert card.overall == card.base_rating
        # When potential >= target, expect exact hit
        if card.potential >= target and card.overall != target:
            misses += 1
    assert misses == 0


def test_potential_ceiling_terminates() -> None:
    """If target exceeds potential, land on capped True OVR without hanging."""
    r = random.Random(99)
    # Force a low-potential path by using high age + Common and checking termination
    card = create_player_card(
        position="MID",
        rarity="Common",
        target_ovr=64,
        first_name="Ceil",
        last_name="Test",
        age=34,
        rng=r,
    )
    assert 10 <= card.pac <= 99
    assert card.overall == calculate_true_ovr(
        card.position,
        {
            "pac": card.pac,
            "sho": card.sho,
            "pas": card.pas,
            "dri": card.dri,
            "def": card.def_stat,
            "phy": card.phy,
        },
        [],
        card.potential,
    )
