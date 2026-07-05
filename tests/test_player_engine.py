# tests/test_player_engine.py
from __future__ import annotations
from player_engine import GameConfig, calculate_level, roll_dynamic_potential, calculate_contract_renewal_cost

def test_calculate_level() -> None:
    # 0 XP starts at level 1
    assert calculate_level(0) == 1
    assert calculate_level(-10) == 1

    # XP required from 1 to 2 is int(100 * 1.12^0) = 100
    assert calculate_level(99) == 1
    assert calculate_level(100) == 2

    # XP required from 2 to 3 is int(100 * 1.12^1) = 112
    # Cumulative needed for level 3 is 100 + 112 = 212
    assert calculate_level(211) == 2
    assert calculate_level(212) == 3

    # XP required from 3 to 4 is int(100 * 1.12^2) = 125
    # Cumulative needed for level 4 is 212 + 125 = 337
    assert calculate_level(336) == 3
    assert calculate_level(337) == 4

def test_roll_dynamic_potential() -> None:
    # If age is not in youth range (16-21), potential won't rise
    assert roll_dynamic_potential(22, [8.5, 9.0, 8.0, 7.5, 9.0]) == 0
    assert roll_dynamic_potential(15, [8.5, 9.0, 8.0, 7.5, 9.0]) == 0

    # If recent ratings are insufficient
    assert roll_dynamic_potential(18, [6.5, 7.0, 8.0, 7.5, 6.0]) == 0

    # Valid scenario (deterministic mock check since probability is 20%)
    # Let's run a loop to verify it can produce dynamic boosts between 2 and 5
    boosts = set()
    for _ in range(100):
        val = roll_dynamic_potential(18, [8.5, 9.0, 8.0, 7.5, 9.0])
        boosts.add(val)
    
    # Must produce 0 (80% chance) and at least some values in [2, 3, 4, 5] (20% chance)
    assert 0 in boosts
    assert len(boosts) > 1

def test_calculate_contract_renewal_cost() -> None:
    config = GameConfig()
    
    # 40 OVR: (40 - 40)^2 * 0.4 + 50 = 50 coins
    assert calculate_contract_renewal_cost(40, config) == 50
    assert calculate_contract_renewal_cost(30, config) == 50  # Clamps to 40 OVR

    # 80 OVR: (80 - 40)^2 * 0.4 + 50 = 1600 * 0.4 + 50 = 640 + 50 = 690 coins
    assert calculate_contract_renewal_cost(80, config) == 690
