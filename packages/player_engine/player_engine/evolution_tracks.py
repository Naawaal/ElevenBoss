"""Evolution track definitions — single source of truth."""
from __future__ import annotations

EVOLUTION_TRACKS: dict[str, dict] = {
    "pace_boost": {
        "name": "⚡ Pace Masterclass",
        "description": "Improve player speed and burst.",
        "metric": "matches",
        "matches_required": 3,
        "goal": 3,
        "reward_stat": "pac",
        "reward_val": 5,
        "min_ovr": 0,
        "min_player_level": 5,
        "repeatable": False,
    },
    "shooting_star": {
        "name": "🎯 Shooting Star",
        "description": "Drill clinical shooting and finishing.",
        "metric": "matches",
        "matches_required": 3,
        "goal": 3,
        "reward_stat": "sho",
        "reward_val": 5,
        "min_ovr": 0,
        "min_player_level": 10,
        "repeatable": False,
    },
    "def_wall": {
        "name": "🧱 Defensive Wall",
        "description": "Construct rock-solid defense foundation.",
        "metric": "matches",
        "matches_required": 3,
        "goal": 3,
        "reward_stat": "def",
        "reward_val": 5,
        "min_ovr": 0,
        "min_player_level": 8,
        "repeatable": False,
    },
}

CANCEL_FEE_COINS = 100
MAX_ACTIVE_EVOLUTIONS = 3
# Mirrors game_config evolution_cooldown_hours seed (046); RPC reads live config
EVOLUTION_START_COOLDOWN_HOURS = 6
EVOLUTION_START_ENERGY = 25
EVOLUTION_START_FLAT = 500
EVOLUTION_START_OVR_MULT = 5
# Legacy alias (pre-v2 used 10×OVR only)
EVOLUTION_START_COIN_MULTIPLIER = EVOLUTION_START_OVR_MULT

VALID_TRACK_IDS = frozenset(EVOLUTION_TRACKS.keys())


def track_goal(track_id: str) -> int:
    return int(EVOLUTION_TRACKS[track_id]["matches_required"])


def track_min_player_level(track_id: str) -> int:
    return int(EVOLUTION_TRACKS[track_id].get("min_player_level", 1))


def evolution_unlocked(track_id: str, player_level: int) -> bool:
    return player_level >= track_min_player_level(track_id)


def evolution_start_cost(ovr: int) -> tuple[int, int]:
    """Returns (energy, coins) for starting an evolution on an OVR-rated card."""
    return EVOLUTION_START_ENERGY, EVOLUTION_START_FLAT + EVOLUTION_START_OVR_MULT * ovr


def format_cooldown_remaining(seconds: int) -> str:
    """Format seconds as e.g. '7h 32m' for hub display."""
    if seconds <= 0:
        return "Ready"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
