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

def test_calculate_true_ovr() -> None:
    from player_engine import calculate_true_ovr
    # Base check for MID (weights: pac 0.10, sho 0.15, pas 0.25, dri 0.20, def 0.15, phy 0.15)
    stats = {"pac": 80, "sho": 70, "pas": 85, "dri": 80, "def": 60, "phy": 65}
    # base_ovr = 80*0.10 + 70*0.15 + 85*0.25 + 80*0.20 + 60*0.15 + 65*0.15
    # = 8.0 + 10.5 + 21.25 + 16.0 + 9.0 + 9.75 = 74.5
    assert calculate_true_ovr("MID", stats, [], 90) == 74 # floor(74.5) = 74
    
    # Check playstyle synergy bonus (MID has Playmaker, Speedster)
    # 1 synergy: +1
    assert calculate_true_ovr("MID", stats, ["Playmaker"], 90) == 75
    # 2 synergies: +2
    assert calculate_true_ovr("MID", stats, ["Playmaker", "Speedster"], 90) == 76
    # 3 synergies: capped at +2
    assert calculate_true_ovr("MID", stats, ["Playmaker", "Speedster", "Power Header"], 90) == 76

    # Check potential ceiling clamp
    assert calculate_true_ovr("MID", stats, ["Playmaker", "Speedster"], 75) == 75

def test_apply_match_form() -> None:
    from player_engine import apply_match_form
    # morale >= 90: +2
    assert apply_match_form(75, 95) == 77
    # morale >= 75: +1
    assert apply_match_form(75, 80) == 76
    # morale <= 25: -2
    assert apply_match_form(75, 20) == 73
    # morale <= 40: -1
    assert apply_match_form(75, 35) == 74
    # normal range (41-74): no change
    assert apply_match_form(75, 50) == 75

