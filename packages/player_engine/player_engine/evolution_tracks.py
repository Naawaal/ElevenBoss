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

VALID_TRACK_IDS = frozenset(EVOLUTION_TRACKS.keys())


def track_goal(track_id: str) -> int:
    return int(EVOLUTION_TRACKS[track_id]["matches_required"])
