# packages/economy/economy/calculator.py
from __future__ import annotations

RARITY_CAPS: dict[str, int] = {
    "Common": 75,
    "Rare": 84,
    "Epic": 90,
    "Legendary": 99,
}

def level_up_cost(current_level: int) -> int:
    """Calculates coin cost to level up from current_level to current_level + 1."""
    if current_level < 1:
        return 0
    # cost = (current_level ^ 1.5) * 100 rounded to nearest 10
    raw_cost = (current_level ** 1.5) * 100
    return int(round(raw_cost / 10.0) * 10)

def rarity_rating_cap(rarity: str) -> int:
    """Returns the maximum overall rating for a given card rarity."""
    return RARITY_CAPS.get(rarity, 99)

def compute_new_overall(level: int, base_rating: int, rarity: str) -> int:
    """Calculates overall rating at a given level, respecting rarity caps."""
    cap = rarity_rating_cap(rarity)
    overall = base_rating + (level - 1)
    return min(overall, cap)
