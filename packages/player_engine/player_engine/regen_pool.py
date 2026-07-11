# packages/player_engine/player_engine/regen_pool.py
"""Regen scouting pool generation when veterans retire (Phase D)."""
from __future__ import annotations

import random
from typing import Literal

from .created_card import CreatedPlayerCard
from .player_factory import create_player_card

RegenRarity = Literal["Common", "Rare", "Epic"]


def regen_rarity_for_ovr(retired_ovr: int, rng: random.Random) -> RegenRarity:
    """Rarity weights by peak OVR (FR-014). Below 75 returns Common defensively."""
    roll = rng.random()
    if retired_ovr >= 85:
        return "Epic" if roll < 0.50 else "Rare"
    if retired_ovr >= 80:
        return "Rare" if roll < 0.60 else "Common"
    if retired_ovr >= 75:
        return "Rare" if roll < 0.20 else "Common"
    return "Common"


def generate_regen_from_retired(
    retired: dict,
    *,
    first_names: list[str],
    last_names: list[str],
    rng: random.Random | None = None,
) -> CreatedPlayerCard:
    """Spawn a youth regen inspired by a retired card (same position, POT ≈ base_potential)."""
    r = rng or random
    position = retired["position"]
    retired_ovr = int(retired.get("overall", 70))
    base_pot = int(retired.get("base_potential") or retired.get("potential") or retired_ovr)

    lo = max(55, min(65, retired_ovr - 20))
    hi = min(70, max(60, retired_ovr - 10))
    target_ovr = r.randint(lo, hi)
    age = r.randint(16, 19)

    rarity = regen_rarity_for_ovr(retired_ovr, r)

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
    return card.model_copy(
        update={
            "potential": pot,
            "base_potential": pot,
            "source_card_id": str(retired["id"]),
        }
    )
