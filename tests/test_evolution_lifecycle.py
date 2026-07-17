"""Evolution lifecycle helpers."""
from __future__ import annotations

from player_engine import (
    EVOLUTION_START_FLAT,
    EVOLUTION_START_OVR_MULT,
    EVOLUTION_START_COOLDOWN_HOURS,
    EVOLUTION_START_ENERGY,
    EVOLUTION_TRACKS,
    MAX_ACTIVE_EVOLUTIONS,
    VALID_TRACK_IDS,
    evolution_start_cost,
    format_cooldown_remaining,
    track_goal,
)


def test_evolution_tracks_defined() -> None:
    assert len(EVOLUTION_TRACKS) == 3
    assert VALID_TRACK_IDS == frozenset({"pace_boost", "shooting_star", "def_wall"})
    assert track_goal("pace_boost") == 3


def test_track_has_legacy_goal_alias() -> None:
    for track in EVOLUTION_TRACKS.values():
        assert track["goal"] == track["matches_required"]


def test_pacing_constants() -> None:
    assert MAX_ACTIVE_EVOLUTIONS == 3
    assert EVOLUTION_START_COOLDOWN_HOURS == 6
    assert EVOLUTION_START_ENERGY == 25
    assert EVOLUTION_START_FLAT == 500
    assert EVOLUTION_START_OVR_MULT == 5


def test_evolution_start_cost() -> None:
    assert evolution_start_cost(78) == (25, 500 + 5 * 78)
    assert evolution_start_cost(0) == (25, 500)


def test_format_cooldown_remaining() -> None:
    assert format_cooldown_remaining(0) == "Ready"
    assert format_cooldown_remaining(27120) == "7h 32m"
    assert format_cooldown_remaining(3600) == "1h"
    assert format_cooldown_remaining(90) == "1m"
