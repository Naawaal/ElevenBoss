# packages/economy/economy/engine.py
from __future__ import annotations
from .config import GameConfig

def calculate_weekly_wages(squad: list[dict], config: GameConfig) -> int:
    """Calculates weekly wages for a list of players based on their OVR.

    Formula: (OVR - 40)^2 * wage_scale_factor + 10
    """
    total_wages = 0
    for p in squad:
        ovr = p.get("overall", p.get("base_rating", 50))
        calc_ovr = max(40, ovr)
        wage = int((calc_ovr - 40) ** 2 * config.wage_scale_factor + 10)
        total_wages += wage
    return total_wages

def generate_agent_offer(player_ovr: int, player_rarity: str, config: GameConfig) -> int:
    """Generates a coin purchase offer from a transfer market agent.

    Formula: ((OVR - 45)^2.5 * 1.5 + 50) * rarity_multiplier
    """
    calc_ovr = max(45, player_ovr)
    base_val = (calc_ovr - 45) ** 2.5 * 1.5 + 50
    
    rarity_mults = {
        "Common": 1.0,
        "Rare": 1.5,
        "Epic": 2.2,
        "Legendary": 3.5
    }
    mult = rarity_mults.get(player_rarity, 1.0)
    return int(base_val * mult)
