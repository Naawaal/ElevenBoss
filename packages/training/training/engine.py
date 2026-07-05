# packages/training/training/engine.py
from __future__ import annotations
from economy.config import GameConfig

def calculate_xp_gain(drill: str, player_lvl: int, config: GameConfig) -> int:
    """Calculates XP gained from a drill using diminishing returns based on player level.

    Formula: base_xp * (1.0 / (1.0 + 0.05 * (level - 1)))
    """
    base_xp = config.drill_xp.get(drill, 0)
    lvl = max(1, player_lvl)
    mult = 1.0 / (1.0 + 0.05 * (lvl - 1))
    return int(base_xp * mult)
