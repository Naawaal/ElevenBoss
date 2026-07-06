# packages/player_engine/player_engine/__init__.py
from __future__ import annotations

from .config import GameConfig
from .generated_player import GeneratedPlayer
from .potential import (
    RARITY_POT_CAPS,
    apply_dynamic_potential_boost,
    format_potential_display,
    generate_potential,
    potential_tier_label,
)
from .engine import (
    calculate_level,
    roll_dynamic_potential,
    calculate_contract_renewal_cost,
    calculate_true_ovr,
    apply_match_form,
)
from .progression_gates import (
    STAT_KEYS,
    can_gain_stat_progression,
    detect_stat_inflation,
    rebalance_stats_to_ovr,
    simulate_legacy_stat_drill,
    stats_from_card,
)
from .evolution_tracks import (
    CANCEL_FEE_COINS,
    EVOLUTION_START_COIN_MULTIPLIER,
    EVOLUTION_START_COOLDOWN_HOURS,
    EVOLUTION_START_ENERGY,
    EVOLUTION_TRACKS,
    MAX_ACTIVE_EVOLUTIONS,
    VALID_TRACK_IDS,
    evolution_start_cost,
    format_cooldown_remaining,
    track_goal,
)

__all__ = [
    "GameConfig",
    "RARITY_POT_CAPS",
    "GeneratedPlayer",
    "apply_dynamic_potential_boost",
    "format_potential_display",
    "generate_potential",
    "potential_tier_label",
    "calculate_level",
    "roll_dynamic_potential",
    "calculate_contract_renewal_cost",
    "calculate_true_ovr",
    "apply_match_form",
    "STAT_KEYS",
    "can_gain_stat_progression",
    "detect_stat_inflation",
    "rebalance_stats_to_ovr",
    "simulate_legacy_stat_drill",
    "stats_from_card",
    "generate_player",
    "generate_squad",
    "EVOLUTION_TRACKS",
    "VALID_TRACK_IDS",
    "CANCEL_FEE_COINS",
    "MAX_ACTIVE_EVOLUTIONS",
    "EVOLUTION_START_COOLDOWN_HOURS",
    "EVOLUTION_START_ENERGY",
    "EVOLUTION_START_COIN_MULTIPLIER",
    "evolution_start_cost",
    "format_cooldown_remaining",
    "track_goal",
]
