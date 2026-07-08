# packages/player_engine/player_engine/regen_pool.py
"""Regen scouting pool generation when veterans retire (Phase D)."""
from __future__ import annotations

import random

from .player_factory import create_player_card


def generate_regen_from_retired(
    retired: dict,
    *,
    first_names: list[str],
    last_names: list[str],
    rng: random.Random | None = None,
) -> dict:
    """Spawn a youth regen inspired by a retired card (same position, POT ≈ base_potential)."""
    r = rng or random
    position = retired["position"]
    retired_ovr = int(retired.get("overall", 70))
    base_pot = int(retired.get("base_potential") or retired.get("potential") or retired_ovr)

    lo = max(55, min(65, retired_ovr - 20))
    hi = min(70, max(60, retired_ovr - 10))
    target_ovr = r.randint(lo, hi)
    age = r.randint(16, 19)

    rarity = "Common"
    if retired_ovr >= 80 and r.random() < 0.35:
        rarity = "Rare"
    elif retired_ovr >= 85 and r.random() < 0.15:
        rarity = "Epic"

    pot = max(target_ovr, min(94, base_pot + r.randint(-3, 5)))

    card = create_player_card(
        position=position,
        rarity=rarity,
        target_ovr=target_ovr,
        first_name=r.choice(first_names),
        last_name=r.choice(last_names),
        age=age,
        rng=r,
    )
    card["potential"] = pot
    card["base_potential"] = pot
    card["source_card_id"] = str(retired["id"])
    return card
