# packages/player_engine/player_engine/progression_gates.py
"""Pure gates for stat progression (mirrors DB RPC rules)."""
from __future__ import annotations

import random
from typing import Any

from .engine import POSITION_WEIGHTS, calculate_true_ovr

STAT_KEYS = ("pac", "sho", "pas", "dri", "def", "phy")


def stats_from_card(card: dict[str, Any]) -> dict[str, int]:
    return {k: int(card.get(k, 50)) for k in STAT_KEYS}


def can_gain_stat_progression(
    *,
    overall: int,
    potential: int,
    stat_value: int,
) -> tuple[bool, str]:
    """Return whether a +1 stat drill or similar gain is allowed."""
    if stat_value >= 99:
        return False, "Stat is already at maximum"
    if overall >= potential:
        return False, "Player is already at maximum overall for their potential"
    return True, ""


def simulate_legacy_stat_drill(
    *,
    overall: int,
    potential: int,
    stat_value: int,
    position: str = "FWD",
) -> dict:
    """Model pre-fix process_stat_drill: may charge with 0 levels at stat 99."""
    from .engine import calculate_true_ovr

    stats = {"pac": 60, "sho": stat_value, "pas": 60, "dri": 60, "def": 60, "phy": 60}
    levels = 0
    charged = True
    new_stat = stat_value
    if stat_value >= 99:
        levels = 0
        new_stat = 99
    else:
        new_stat = stat_value + 1
        levels = 1
        stats["sho"] = new_stat
    new_ovr = calculate_true_ovr(position, stats, [], potential)
    return {
        "levels_gained": levels,
        "charged": charged,
        "new_stat": new_stat,
        "new_ovr": new_ovr,
        "overall_before": overall,
        "potential": potential,
    }


def detect_stat_inflation(
    position: str,
    stats: dict[str, int],
    playstyles: list[str],
    overall: int,
    potential: int,
    *,
    hidden_threshold: int = 1,
) -> tuple[bool, dict[str, int]]:
    """True when stats imply more power than the stored OVR / POT ceiling shows."""
    capped = calculate_true_ovr(position, stats, playstyles, potential)
    uncapped = calculate_true_ovr(position, stats, playstyles, 99)
    hidden = uncapped - capped
    max_stat = max(stats.values())
    inflated = hidden > hidden_threshold
    return inflated, {
        "capped_ovr": capped,
        "uncapped_ovr": uncapped,
        "hidden_power": hidden,
        "max_stat": max_stat,
        "max_stat_delta": max_stat - overall,
        "stored_overall": overall,
    }


def rebalance_stats_to_ovr(
    position: str,
    target_ovr: int,
    playstyles: list[str],
    potential: int,
    *,
    rng: random.Random,
) -> dict[str, int]:
    """Roll position-weighted stats that match target OVR under the POT cap."""
    weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS["MID"])
    stats: dict[str, int] = {}
    for attr, weight in weights.items():
        if weight >= 0.25:
            stats[attr] = target_ovr + rng.randint(2, 12)
        elif weight >= 0.15:
            stats[attr] = target_ovr + rng.randint(-5, 5)
        else:
            stats[attr] = target_ovr + rng.randint(-20, -5)
        stats[attr] = max(10, min(99, stats[attr]))

    new_ovr = calculate_true_ovr(position, stats, playstyles, potential)
    diff = target_ovr - new_ovr
    attempts = 0
    while diff != 0 and attempts < 20:
        shift = 1 if diff > 0 else -1
        for attr in sorted(stats, key=lambda a: weights[a], reverse=True):
            if weights[attr] <= 0:
                continue
            nxt = max(10, min(99, stats[attr] + shift))
            if nxt != stats[attr]:
                stats[attr] = nxt
                break
        new_ovr = calculate_true_ovr(position, stats, playstyles, potential)
        diff = target_ovr - new_ovr
        attempts += 1
    return stats
