# packages/player_engine/player_engine/player_factory.py
"""Unified procedural player creation for gacha / intake sources."""
from __future__ import annotations

import random
from datetime import date

from .age_manager import dob_from_age
from .engine import calculate_true_ovr
from .potential import generate_potential

_POSITION_WEIGHTS = {
    "FWD": {"pac": 0.20, "sho": 0.35, "pas": 0.10, "dri": 0.20, "def": 0.05, "phy": 0.10},
    "MID": {"pac": 0.10, "sho": 0.15, "pas": 0.25, "dri": 0.20, "def": 0.15, "phy": 0.15},
    "DEF": {"pac": 0.15, "sho": 0.05, "pas": 0.10, "dri": 0.05, "def": 0.40, "phy": 0.25},
    "GK": {"pac": 0.15, "sho": 0.00, "pas": 0.15, "dri": 0.00, "def": 0.50, "phy": 0.20},
}


def roll_creation_age(rng: random.Random | None = None) -> int:
    r = rng or random
    roll = r.random()
    if roll < 0.40:
        return r.randint(16, 21)
    if roll < 0.80:
        return r.randint(22, 27)
    if roll < 0.95:
        return r.randint(28, 32)
    return r.randint(33, 36)


def create_player_card(
    *,
    position: str,
    rarity: str,
    target_ovr: int,
    first_name: str,
    last_name: str,
    age: int | None = None,
    reference_date: date | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Return card dict for RPC payloads (stats, age, date_of_birth, potential)."""
    r = rng or random
    age_val = age if age is not None else roll_creation_age(r)
    jitter = r.randint(-120, 120)
    dob = dob_from_age(age_val, reference=reference_date, day_jitter=jitter)

    potential = generate_potential(target_ovr, age_val, rarity, position, rng=r)
    weights = _POSITION_WEIGHTS.get(position, _POSITION_WEIGHTS["MID"])
    stats: dict[str, int] = {}
    for attr, weight in weights.items():
        if weight >= 0.25:
            stats[attr] = target_ovr + r.randint(2, 12)
        elif weight >= 0.15:
            stats[attr] = target_ovr + r.randint(-5, 5)
        else:
            stats[attr] = target_ovr + r.randint(-20, -5)
        stats[attr] = max(10, min(99, stats[attr]))

    overall = calculate_true_ovr(position, stats, [], potential)
    diff = target_ovr - overall
    attempts = 0
    while diff != 0 and attempts < 10:
        shift = 1 if diff > 0 else -1
        for attr in stats:
            if weights[attr] > 0:
                stats[attr] = max(10, min(99, stats[attr] + shift))
        overall = calculate_true_ovr(position, stats, [], potential)
        diff = target_ovr - overall
        attempts += 1

    return {
        "name": f"{first_name} {last_name}",
        "position": position,
        "rarity": rarity,
        "base_rating": overall,
        "overall": overall,
        "pac": stats["pac"],
        "sho": stats["sho"],
        "pas": stats["pas"],
        "dri": stats["dri"],
        "def": stats["def"],
        "phy": stats["phy"],
        "potential": potential,
        "base_potential": potential,
        "age": age_val,
        "date_of_birth": dob.isoformat(),
    }
