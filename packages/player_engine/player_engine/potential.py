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


def rarity_potential_cap(rarity: str) -> int:
    """Absolute POT ceiling for a rarity. Unknown rarity fails closed."""
    try:
        return RARITY_POT_CAPS[rarity]
    except KeyError as exc:
        raise ValueError(f"Unsupported rarity: {rarity!r}") from exc


def clamp_potential(potential: int, rarity: str) -> int:
    return min(int(potential), rarity_potential_cap(rarity), MAX_POTENTIAL)


def validate_potential_integrity(
    *,
    rarity: str,
    overall: int,
    potential: int,
    base_potential: int | None,
) -> None:
    cap = rarity_potential_cap(rarity)
    if int(potential) > cap:
        raise ValueError(f"{rarity} POT {potential} exceeds rarity cap {cap}")
    if base_potential is not None and int(base_potential) > cap:
        raise ValueError(f"{rarity} base POT {base_potential} exceeds rarity cap {cap}")
    if int(overall) > int(potential):
        raise ValueError(f"OVR {overall} exceeds POT {potential}")


def effective_potential(*, rarity: str, potential: int) -> int:
    """Progression ceiling while stored POT may still be dirty."""
    return min(int(potential), rarity_potential_cap(rarity))


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
    Illegal overall above the rarity cap is rejected — never manufacture POT > cap.
    """
    r = rng or random
    overall = max(1, min(99, overall))
    age = max(15, min(45, age))
    cap = rarity_potential_cap(rarity)

    if overall > cap:
        raise ValueError(
            f"{rarity} card cannot be generated at {overall} OVR; maximum is {cap}"
        )

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
    pot = min(pot, cap, MAX_POTENTIAL)
    # overall <= cap already established — cannot break rarity ceiling
    return max(MIN_POTENTIAL, overall, int(pot))


def apply_dynamic_potential_boost(
    current_potential: int,
    base_potential: int,
    boost: int,
    rarity: str,
) -> int:
    """Raise current potential after exceptional youth performance (inside rarity)."""
    if boost <= 0:
        return current_potential
    cap = rarity_potential_cap(rarity)
    ceiling = min(cap, int(base_potential) + MAX_DYNAMIC_BOOST)
    return min(int(current_potential) + max(int(boost), 0), ceiling)


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
