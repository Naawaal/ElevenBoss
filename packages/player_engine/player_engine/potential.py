# packages/player_engine/player_engine/potential.py
"""Dynamic player potential generation and display helpers."""
from __future__ import annotations

import random
from typing import Final

RARITY_POT_CAPS: Final[dict[str, int]] = {
    "Common": 75,
    "Rare": 85,
    "Epic": 92,
    "Legendary": 99,
}

POSITION_POT_BONUS: Final[dict[str, int]] = {
    "FWD": 1,
    "GK": 1,
    "DEF": 0,
    "MID": 0,
}

MIN_POTENTIAL: Final[int] = 40
MAX_POTENTIAL: Final[int] = 99
MAX_DYNAMIC_BOOST: Final[int] = 10


def generate_potential(
    overall: int,
    age: int,
    rarity: str = "Common",
    position: str = "MID",
    *,
    rng: random.Random | None = None,
) -> int:
    """Assign a realistic potential ceiling from age, rarity, OVR, and position.

    Younger and rarer players trend higher; veterans peak near current OVR.
    """
    r = rng or random
    overall = max(1, min(99, overall))
    age = max(15, min(45, age))
    rarity_cap = RARITY_POT_CAPS.get(rarity, RARITY_POT_CAPS["Common"])

    # Normal-ish base (mean 70, σ 10) — ponytail: gauss is stdlib, good enough for POT rolls
    base = int(round(r.gauss(70, 10)))
    base = max(MIN_POTENTIAL, min(MAX_POTENTIAL, base))

    if age <= 21:
        age_mod = int((22 - age) * 1.2) + r.randint(0, 5)
    elif age <= 27:
        age_mod = r.randint(0, 4)
    elif age <= 32:
        age_mod = r.randint(-4, 1)
    else:
        age_mod = r.randint(-18, -2)

    pos_mod = POSITION_POT_BONUS.get(position, 0)
    raw = base + age_mod + pos_mod

    if age <= 21:
        floor = overall + r.randint(5, 15)
    elif age <= 27:
        floor = overall + r.randint(2, 10)
    elif age <= 32:
        floor = overall + r.randint(1, 5)
    else:
        floor = overall + r.randint(0, 2)

    pot = max(raw, floor, overall)
    pot = min(pot, rarity_cap, MAX_POTENTIAL)
    # Never below current OVR (legacy cards may already exceed rarity cap)
    return max(MIN_POTENTIAL, overall, int(pot))


def apply_dynamic_potential_boost(
    current_potential: int,
    base_potential: int,
    boost: int,
) -> int:
    """Raise current potential after exceptional youth performance (capped at base + 10)."""
    if boost <= 0:
        return current_potential
    ceiling = min(MAX_POTENTIAL, base_potential + MAX_DYNAMIC_BOOST)
    return min(ceiling, current_potential + boost)


def potential_tier_label(potential: int) -> str:
    if potential >= 90:
        return "World Class"
    if potential >= 85:
        return "High Potential"
    if potential >= 75:
        return "Good Growth"
    if potential >= 65:
        return "Moderate"
    return "Limited"


def format_potential_display(potential: int | None, age: int | None = None) -> str:
    pot = potential if potential is not None else 0
    tier = potential_tier_label(pot)
    age_part = f"{age} yrs / " if age is not None else ""
    suffix = f" · {tier}" if pot >= 85 else ""
    return f"{age_part}📊 {pot} POT{suffix}"
