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

def generate_agent_offer(
    player_ovr: int,
    player_rarity: str,
    config: GameConfig,
    *,
    age: int | None = None,
    potential: int | None = None,
) -> int:
    """Generates a coin purchase offer from a transfer market agent.

    Formula: ((OVR - 45)^2.5 * 1.5 + 50) * rarity_multiplier * age_factor
    """
    calc_ovr = max(45, player_ovr)
    base_val = (calc_ovr - 45) ** 2.5 * 1.5 + 50

    rarity_mults = {
        "Common": 1.0,
        "Rare": 1.5,
        "Epic": 2.2,
        "Legendary": 3.5,
    }
    mult = rarity_mults.get(player_rarity, 1.0)
    offer = int(base_val * mult)

    if age is not None:
        if age < 23:
            age_factor = 1.2
        elif age <= 28:
            age_factor = 1.0
        elif age <= 32:
            age_factor = 0.8
        else:
            age_factor = 0.5
        offer = int(offer * age_factor)

    if potential is not None and potential > player_ovr:
        pot_bonus = 1.0 + min(0.15, (potential - player_ovr) * 0.02)
        offer = int(offer * pot_bonus)

    return max(50, offer)
