# tests/test_economy_flows.py
"""US-25 economy flow unit tests."""
from __future__ import annotations

from economy.flows import (
    EconomyConfig,
    bot_match_coins,
    drill_cost,
    daily_login_reward,
    league_match_coins,
    simulate_casual_day,
    simulate_hardcore_day,
    simulate_days,
)


def test_bot_match_coins_scaled_win():
    assert bot_match_coins("win", 100) == 200
    assert bot_match_coins("win", 600) == 1200
    assert bot_match_coins("draw", 100) == 100
    assert bot_match_coins("loss", 100) == 50


def test_drill_cost_basic_vs_advanced():
    basic_coins, basic_energy = drill_cost(60, 5)
    adv_coins, adv_energy = drill_cost(60, 12)
    assert basic_coins == 100 + 2 * 60
    assert basic_energy == 10
    assert adv_coins == 300 + 3 * 60
    assert adv_energy == 15


def test_league_match_coins_tiers():
    assert league_match_coins("Grassroots") == 250
    assert league_match_coins("Legendary") == 400


def test_daily_login_streak_cap():
    assert daily_login_reward(1) == 100
    assert daily_login_reward(2) == 110
    assert daily_login_reward(10) == 150  # 100 + cap 50


def test_casual_day_near_balanced():
    b = simulate_casual_day(ovr=60, player_level=5, wins=5, drills=5)
    assert b.income == 5 * 200 + 100
    assert b.expenses == 5 * 220
    assert b.net == 0


def test_hardcore_day_net_negative():
    b = simulate_hardcore_day()
    assert b.net < 0


def test_30_day_sim_no_hyperinflation_casual():
    series = simulate_days("casual", 30)
    assert series[-1] < 50_000
