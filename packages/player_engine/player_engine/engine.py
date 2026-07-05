# packages/player_engine/player_engine/engine.py
from __future__ import annotations
import random
import math
from .config import GameConfig

POSITION_WEIGHTS = {
    "FWD": {"pac": 0.20, "sho": 0.35, "pas": 0.10, "dri": 0.20, "def": 0.05, "phy": 0.10},
    "MID": {"pac": 0.10, "sho": 0.15, "pas": 0.25, "dri": 0.20, "def": 0.15, "phy": 0.15},
    "DEF": {"pac": 0.15, "sho": 0.05, "pas": 0.10, "dri": 0.05, "def": 0.40, "phy": 0.25},
    "GK": {"pac": 0.15, "sho": 0.00, "pas": 0.15, "dri": 0.00, "def": 0.50, "phy": 0.20}
}

PLAYSTYLE_SYNERGY = {
    "Power Header": ["FWD", "DEF"],
    "Playmaker": ["MID"],
    "Speedster": ["FWD", "MID", "DEF"]
}

def calculate_true_ovr(position: str, stats: dict[str, int], playstyles: list[str], potential: int) -> int:
    """Calculates the dynamic position-weighted OVR for a player card."""
    weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS["MID"])
    
    # 1. Base Weighted Average
    base_ovr = (
        (stats.get("pac", 50) * weights["pac"]) +
        (stats.get("sho", 50) * weights["sho"]) +
        (stats.get("pas", 50) * weights["pas"]) +
        (stats.get("dri", 50) * weights["dri"]) +
        (stats.get("def", 50) * weights["def"]) +
        (stats.get("phy", 50) * weights["phy"])
    )
    
    # 2. PlayStyle Synergy Bonus (+1 OVR per matching playstyle, capped at +2)
    bonus = 0
    for ps in playstyles:
        if position in PLAYSTYLE_SYNERGY.get(ps, []):
            bonus += 1
    bonus = min(bonus, 2)
    
    # 3. Apply potential ceiling and round down
    calculated_ovr = math.floor(base_ovr + bonus)
    return min(calculated_ovr, potential)

def apply_match_form(base_ovr: int, morale: int) -> int:
    """Calculates temporary Match OVR based on morale (0-100)."""
    if morale >= 90:
        return base_ovr + 2
    if morale >= 75:
        return base_ovr + 1
    if morale <= 25:
        return base_ovr - 2
    if morale <= 40:
        return base_ovr - 1
    return base_ovr

def calculate_level(xp: int) -> int:
    """Calculates player card level from cumulative XP.

    Formula curve is based on level-up requirements of 100 * 1.12^(L-1).
    """
    if xp <= 0:
        return 1
    lvl = 1
    accumulated_xp = 0
    while True:
        needed = int(100 * (1.12 ** (lvl - 1)))
        if xp >= accumulated_xp + needed:
            accumulated_xp += needed
            lvl += 1
        else:
            break
    return lvl

def roll_dynamic_potential(age: int, recent_ratings: list[float]) -> int:
    """Computes dynamic potential increase (+2 to +5) for young players (age 16-21)

    who achieved at least 3 ratings >= 8.0 in their last 5 matches.
    Has a 20% success probability.
    """
    if not (16 <= age <= 21):
        return 0
    
    last_5 = recent_ratings[-5:]
    if len(last_5) < 3:
        return 0
        
    high_ratings = sum(1 for r in last_5 if r >= 8.0)
    if high_ratings >= 3:
        if random.random() < 0.20:
            return random.randint(2, 5)
    return 0

def calculate_contract_renewal_cost(ovr: int, config: GameConfig) -> int:
    """Calculates coin renewal fee based on player overall rating."""
    calc_ovr = max(40, ovr)
    return int((calc_ovr - 40) ** 2 * 0.4 + 50)
