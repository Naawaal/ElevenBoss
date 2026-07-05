# packages/player_engine/player_engine/engine.py
from __future__ import annotations
import random
from .config import GameConfig

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
