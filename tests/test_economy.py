# tests/test_economy.py
from __future__ import annotations
from economy import GameConfig, calculate_weekly_wages, generate_agent_offer

def test_calculate_weekly_wages() -> None:
    config = GameConfig(wage_scale_factor=1.2)
    
    # 1. Empty squad
    assert calculate_weekly_wages([], config) == 0

    # 2. Squad of players with OVR
    squad = [
        {"overall": 40},  # (40-40)^2 * 1.2 + 10 = 10
        {"overall": 50},  # (50-40)^2 * 1.2 + 10 = 100 * 1.2 + 10 = 130
        {"overall": 35},  # clamped to 40: (40-40)^2 * 1.2 + 10 = 10
    ]
    assert calculate_weekly_wages(squad, config) == 10 + 130 + 10

def test_generate_agent_offer() -> None:
    config = GameConfig()
    
    # Common player OVR 50
    # ((50 - 45)^2.5 * 1.5 + 50) * 1.0 = (5^2.5 * 1.5 + 50) = (55.9 * 1.5 + 50) = (83.85 + 50) = 133.85 -> 133
    offer_common = generate_agent_offer(50, "Common", config)
    assert offer_common == 133

    # Legendary player OVR 80
    # ((80 - 45)^2.5 * 1.5 + 50) * 3.5
    # 35^2.5 = 7247.06 -> *1.5 = 10870.6 -> +50 = 10920.6 -> *3.5 = 38222.1 -> 38222
    offer_legendary = generate_agent_offer(80, "Legendary", config)
    assert offer_legendary == 38222
