# tests/test_rarity_potential_integrity.py
from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from player_engine import (
    RARITY_POT_CAPS,
    CreatedPlayerCard,
    apply_dynamic_potential_boost,
    clamp_potential,
    create_player_card,
    generate_potential,
    generate_regen_from_retired,
    generate_youth_intake_cards,
    rarity_potential_cap,
    validate_potential_integrity,
)


def test_rarity_cap_table() -> None:
    assert rarity_potential_cap("Common") == 75
    assert rarity_potential_cap("Rare") == 85
    assert rarity_potential_cap("Epic") == 92
    assert rarity_potential_cap("Legendary") == 99
    with pytest.raises(ValueError, match="Unsupported rarity"):
        rarity_potential_cap("Mythic")


def test_boundary_pass_fail() -> None:
    for rarity, cap in RARITY_POT_CAPS.items():
        validate_potential_integrity(
            rarity=rarity, overall=cap, potential=cap, base_potential=cap
        )
        with pytest.raises(ValueError):
            validate_potential_integrity(
                rarity=rarity,
                overall=cap,
                potential=cap + 1,
                base_potential=cap,
            )


def test_epic_dynamic_boost_caps_at_92() -> None:
    assert apply_dynamic_potential_boost(92, 90, 5, "Epic") == 92


def test_created_card_rejects_illegal_pot() -> None:
    with pytest.raises((ValidationError, ValueError)):
        CreatedPlayerCard(
            name="Bad Epic",
            position="MID",
            rarity="Epic",
            role="Balanced",
            base_rating=88,
            overall=88,
            pac=80,
            sho=80,
            pas=80,
            dri=80,
            def_stat=80,
            phy=80,
            potential=97,
            base_potential=97,
            age=20,
            date_of_birth="2006-01-01",
        )


def test_factory_rejects_target_above_cap() -> None:
    with pytest.raises(ValueError, match="maximum is 75"):
        create_player_card(
            position="MID",
            rarity="Common",
            target_ovr=76,
            first_name="A",
            last_name="B",
            rng=random.Random(1),
        )


def test_regen_never_exceeds_rarity() -> None:
    rng = random.Random(42)
    for i in range(40):
        retired = {
            "id": f"00000000-0000-0000-0000-{i:012d}",
            "position": "MID",
            "overall": 88,
            "base_potential": 94,
            "potential": 94,
        }
        card = generate_regen_from_retired(
            retired,
            first_names=["Ada"],
            last_names=["Lovelace"],
            rng=rng,
        )
        cap = rarity_potential_cap(card.rarity)
        assert card.potential <= cap
        assert card.base_potential <= cap
        assert card.overall <= card.potential


def test_youth_intake_obeys_rarity_ceilings() -> None:
    """V2 academy intake may roll Rare/Epic at L5; still must obey caps."""
    rng = random.Random(7)
    cards = generate_youth_intake_cards(
        5,
        academy_level=5,
        first_names=["Ada"],
        last_names=["Lovelace"],
        rng=rng,
    )
    for card in cards:
        cap = rarity_potential_cap(card.rarity)
        assert card.potential <= cap
        assert card.base_potential <= cap
        assert card.overall <= card.potential


def test_seeded_bulk_generation() -> None:
    rng = random.Random(12345)
    for _ in range(80):
        rarity = rng.choice(list(RARITY_POT_CAPS))
        cap = RARITY_POT_CAPS[rarity]
        ovr = rng.randint(50, min(70, cap))
        age = rng.randint(16, 34)
        pos = rng.choice(["GK", "DEF", "MID", "FWD"])
        pot = generate_potential(ovr, age, rarity, pos, rng=rng)
        assert pot <= cap
        assert pot >= ovr
        assert clamp_potential(99, rarity) == cap
