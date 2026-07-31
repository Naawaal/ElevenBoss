# tests/test_manager_card_gifts.py
"""Pure checks for one-time manager card gift generators (094)."""
from __future__ import annotations

from gacha import (
    MANAGER_CARD_GIFTS_CAMPAIGN,
    generate_manager_gift_epic,
    generate_manager_gift_legendary_mid,
    manager_gift_rng,
)
from player_engine import validate_potential_integrity


def test_manager_gift_epic_bounds_and_determinism() -> None:
    owner = 123456789012345678
    a = generate_manager_gift_epic(owner_id=owner)
    b = generate_manager_gift_epic(owner_id=owner)
    assert a.model_dump() == b.model_dump()
    assert a.rarity == "Epic"
    assert a.position in {"GK", "DEF", "MID", "FWD"}
    assert 75 <= a.overall <= 84
    assert a.potential >= a.overall
    validate_potential_integrity(
        rarity=a.rarity,
        overall=a.overall,
        potential=a.potential,
        base_potential=a.potential,
    )


def test_manager_gift_legendary_mid_fixed_ovr() -> None:
    owner = 976054227459776582
    a = generate_manager_gift_legendary_mid(owner_id=owner)
    b = generate_manager_gift_legendary_mid(owner_id=owner)
    assert a.model_dump() == b.model_dump()
    assert a.rarity == "Legendary"
    assert a.position == "MID"
    assert a.overall == 92
    assert 92 <= a.potential <= 99
    assert a.potential >= a.overall
    validate_potential_integrity(
        rarity=a.rarity,
        overall=a.overall,
        potential=a.potential,
        base_potential=a.potential,
    )


def test_manager_gift_rng_differs_by_slot() -> None:
    owner = 42
    epic = manager_gift_rng(MANAGER_CARD_GIFTS_CAMPAIGN, owner, "epic")
    legend = manager_gift_rng(MANAGER_CARD_GIFTS_CAMPAIGN, owner, "legendary_mid")
    assert epic.randint(0, 10_000) != legend.randint(0, 10_000)
