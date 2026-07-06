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
        "repeatable": False,
    },
}

CANCEL_FEE_COINS = 100
MAX_ACTIVE_EVOLUTIONS = 3
EVOLUTION_START_COOLDOWN_HOURS = 10
EVOLUTION_START_ENERGY = 25
EVOLUTION_START_COIN_MULTIPLIER = 10

VALID_TRACK_IDS = frozenset(EVOLUTION_TRACKS.keys())


def track_goal(track_id: str) -> int:
    return int(EVOLUTION_TRACKS[track_id]["matches_required"])


def evolution_start_cost(ovr: int) -> tuple[int, int]:
    """Returns (energy, coins) for starting an evolution on an OVR-rated card."""
    return EVOLUTION_START_ENERGY, EVOLUTION_START_COIN_MULTIPLIER * ovr


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
