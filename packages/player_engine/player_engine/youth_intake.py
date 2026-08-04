# packages/player_engine/player_engine/youth_intake.py
"""Youth academy intake — V2 rarity-first generation (051)."""

from __future__ import annotations

import random

from economy.facility_effects import (
    youth_ovr_band,
    youth_pot_band,
    youth_rarity_weights,
)

from .created_card import CreatedPlayerCard
from .player_factory import create_player_card
from .potential import (
    clamp_potential,
    rarity_potential_cap,
    validate_potential_integrity,
)

_INTAKE_POSITIONS = ["GK", "DEF", "DEF", "MID", "MID", "FWD"]
_INTAKE_POSITION_WEIGHTS = [10, 25, 25, 20, 20, 20]
_RARITY_ORDER = ("Common", "Rare", "Epic", "Legendary")


def _roll_rarity(
    academy_level: int,
    rng: random.Random,
    *,
    legendary_enabled: bool,
) -> str:
    weights = youth_rarity_weights(academy_level, legendary_enabled=legendary_enabled)
    labels = list(_RARITY_ORDER)
    w = [weights.get(r, 0.0) for r in labels]
    return rng.choices(labels, weights=w, k=1)[0]


def generate_youth_intake_cards(
    count: int | None = None,
    *,
    academy_level: int = 1,
    first_names: list[str],
    last_names: list[str],
    rng: random.Random | None = None,
    legendary_enabled: bool = True,
) -> list[CreatedPlayerCard]:
    """Return typed cards for process_youth_intake RPC (no squad assignment).

    V2: resolve rarity first, then OVR/POT inside that rarity's legal band and ceiling.
    """
    n = 2 if count is None else int(count)
    n = max(1, min(5, n))
    level = max(1, min(5, int(academy_level)))
    r = rng or random
    ovr_lo, ovr_hi = youth_ovr_band(level)

    cards: list[CreatedPlayerCard] = []
    for _ in range(n):
        rarity = _roll_rarity(level, r, legendary_enabled=legendary_enabled)
        cap = rarity_potential_cap(rarity)
        pot_lo, pot_hi = youth_pot_band(rarity)
        pot_hi = min(pot_hi, cap)
        pot_lo = min(pot_lo, pot_hi)

        target_ovr = r.randint(ovr_lo, min(ovr_hi, pot_hi))
        potential = r.randint(max(pot_lo, target_ovr), pot_hi)
        potential = clamp_potential(potential, rarity)
        target_ovr = min(target_ovr, potential)

        position = r.choices(_INTAKE_POSITIONS, weights=_INTAKE_POSITION_WEIGHTS, k=1)[
            0
        ]
        age = r.randint(16, 19)
        card = create_player_card(
            position=position,
            rarity=rarity,
            target_ovr=target_ovr,
            first_name=r.choice(first_names),
            last_name=r.choice(last_names),
            age=age,
            rng=r,
        )
        data = card.model_dump(by_alias=True)
        data["potential"] = potential
        data["base_potential"] = potential
        data["rarity"] = rarity
        # Factory may have rolled its own POT — force V2 values then revalidate
        card = CreatedPlayerCard.model_validate(data)
        validate_potential_integrity(
            rarity=card.rarity,
            overall=card.overall,
            potential=card.potential,
            base_potential=card.base_potential,
        )
        cards.append(card)

    return cards
