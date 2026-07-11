"""Archetype catalog + diversity for procedural card creation."""
from __future__ import annotations

import random
from collections import defaultdict

from player_engine import ARCHETYPES, create_player_card, roll_archetype


def test_catalog_three_per_position() -> None:
    for pos in ("GK", "DEF", "MID", "FWD"):
        names = {a.name for a in ARCHETYPES[pos]}
        assert len(ARCHETYPES[pos]) >= 3
        assert len(names) == len(ARCHETYPES[pos])


def test_fwd_required_archetypes() -> None:
    names = {a.name for a in ARCHETYPES["FWD"]}
    assert {"Poacher", "Speedster", "Complete Forward"} <= names


def test_roll_archetype_seeded_diverse() -> None:
    roles = {roll_archetype("FWD", random.Random(i)).name for i in range(40)}
    assert len(roles) >= 2


def test_fwd_archetype_stat_shapes_diverge() -> None:
    r = random.Random(42)
    by_role: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for _ in range(80):
        card = create_player_card(
            position="FWD",
            rarity="Epic",
            target_ovr=78,
            first_name="Test",
            last_name="Player",
            age=24,
            rng=r,
        )
        by_role[card.role].append((card.sho, card.pac))

    assert len(by_role) >= 2
    if "Poacher" in by_role and "Speedster" in by_role:
        mean_sho_p = sum(s for s, _ in by_role["Poacher"]) / len(by_role["Poacher"])
        mean_pac_s = sum(p for _, p in by_role["Speedster"]) / len(by_role["Speedster"])
        mean_sho_s = sum(s for s, _ in by_role["Speedster"]) / len(by_role["Speedster"])
        mean_pac_p = sum(p for _, p in by_role["Poacher"]) / len(by_role["Poacher"])
        assert mean_sho_p > mean_sho_s
        assert mean_pac_s > mean_pac_p
