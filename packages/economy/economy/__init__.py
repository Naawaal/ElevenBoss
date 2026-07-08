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
from .facility_effects import (
    FACILITY_MAX_LEVEL,
    facility_label,
    facility_upgrade_cost,
    min_matches_for_next_level,
    training_ground_drill_xp_bonus,
    youth_academy_tier,
)

from .scouting_market import scouting_purchase_price

__all__ = [
    "GameConfig",
    "EconomyConfig",
    "FACILITY_MAX_LEVEL",
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
    "facility_label",
    "facility_upgrade_cost",
    "min_matches_for_next_level",
    "training_ground_drill_xp_bonus",
    "youth_academy_tier",
    "scouting_purchase_price",
]
