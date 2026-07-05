# tests/test_training.py
from __future__ import annotations
from economy import GameConfig
from training import calculate_xp_gain

def test_calculate_xp_gain() -> None:
    config = GameConfig(
        drill_xp={
            "cardio": 20,
            "tactics": 100
        }
    )

    # Level 1 player: 1.0 / (1.0 + 0.05 * 0) = 1.0 multiplier -> 20 XP
    assert calculate_xp_gain("cardio", 1, config) == 20
    assert calculate_xp_gain("tactics", 1, config) == 100

    # Level 11 player: 1.0 / (1.0 + 0.05 * 10) = 1.0 / 1.5 = 0.666... multiplier
    # cardio: 20 * (1/1.5) = 13.333 -> 13 XP
    # tactics: 100 * (1/1.5) = 66.666 -> 66 XP
    assert calculate_xp_gain("cardio", 11, config) == 13
    assert calculate_xp_gain("tactics", 11, config) == 66

    # Invalid level defaults to level 1 behavior
    assert calculate_xp_gain("cardio", -5, config) == 20
