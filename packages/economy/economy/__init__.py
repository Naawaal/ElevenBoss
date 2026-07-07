# packages/economy/economy/__init__.py
from __future__ import annotations

from .config import GameConfig
from .engine import calculate_weekly_wages, generate_agent_offer
from .calculator import level_up_cost, rarity_rating_cap, compute_new_overall
from .flows import (
    EconomyConfig,
    bot_match_coins,
    league_match_coins,
    league_entry_fee,
    league_match_coins_for_result,
    friendly_match_coins,
    drill_cost,
    daily_login_reward,
    simulate_casual_day,
    simulate_hardcore_day,
    simulate_days,
)

__all__ = [
    "GameConfig",
    "EconomyConfig",
    "calculate_weekly_wages",
    "generate_agent_offer",
    "level_up_cost",
    "rarity_rating_cap",
    "compute_new_overall",
    "bot_match_coins",
    "league_match_coins",
    "league_entry_fee",
    "league_match_coins_for_result",
    "friendly_match_coins",
    "drill_cost",
    "daily_login_reward",
    "simulate_casual_day",
    "simulate_hardcore_day",
    "simulate_days",
]
