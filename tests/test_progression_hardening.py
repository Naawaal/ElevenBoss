# tests/test_progression_hardening.py
from player_engine import (
    ALLOCATION_DAILY_CAP,
    DRILL_PER_PLAYER_DAILY_CAP,
    MATCH_XP_DAILY_CAP,
    RETRO_MAX_PER_PLAYER,
    RETRO_SCALE_PCT,
    scale_retroactive_reward,
    skill_points_earned_for_level,
)


def test_scale_retroactive_reward_level_10() -> None:
    raw = skill_points_earned_for_level(10)  # 27
    assert scale_retroactive_reward(raw) == 18  # 75% = 20, capped at 18


def test_scale_retroactive_reward_small() -> None:
    assert scale_retroactive_reward(3) == 2  # 75% of 3 = 2


def test_scale_retroactive_reward_zero() -> None:
    assert scale_retroactive_reward(0) == 0


def test_hardening_constants() -> None:
    assert RETRO_SCALE_PCT == 75
    assert RETRO_MAX_PER_PLAYER == 18
    assert ALLOCATION_DAILY_CAP == 15
    assert MATCH_XP_DAILY_CAP == 100
    assert DRILL_PER_PLAYER_DAILY_CAP == 5
