# packages/player_engine/player_engine/youth_intake.py
"""Seasonal youth academy intake — pure generation (Phase B/C)."""
from __future__ import annotations

import random

from economy.facility_effects import youth_academy_tier

from .player_factory import create_player_card

_INTAKE_POSITIONS = ["GK", "DEF", "DEF", "MID", "MID", "FWD"]
_INTAKE_POSITION_WEIGHTS = [10, 25, 25, 20, 20, 20]


def generate_youth_intake_cards(
    count: int | None = None,
    *,
    academy_level: int = 1,
    first_names: list[str],
    last_names: list[str],
    rng: random.Random | None = None,
) -> list[dict]:
    """Return card dicts for process_youth_intake RPC (no squad assignment)."""
    tier = youth_academy_tier(academy_level)
    n = count if count is not None else 3
    n = max(1, min(5, n))
    r = rng or random

    cards: list[dict] = []
    for _ in range(n):
        position = r.choices(_INTAKE_POSITIONS, weights=_INTAKE_POSITION_WEIGHTS, k=1)[0]
        target_ovr = r.randint(tier.ovr_min, tier.ovr_max)
        age = r.randint(16, 19)
        potential = max(target_ovr, r.randint(tier.pot_min, tier.pot_max))
        card = create_player_card(
            position=position,
            rarity="Common",
            target_ovr=target_ovr,
            first_name=r.choice(first_names),
            last_name=r.choice(last_names),
            age=age,
            rng=r,
        )
        card["potential"] = min(tier.pot_max, potential)
        card["base_potential"] = card["potential"]
        cards.append(card)

    if tier.gem_chance > 0 and cards and r.random() < tier.gem_chance:
        gem_idx = r.randrange(len(cards))
        cards[gem_idx]["potential"] = min(tier.pot_max, cards[gem_idx]["potential"] + 5)
        cards[gem_idx]["base_potential"] = cards[gem_idx]["potential"]

    return cards
