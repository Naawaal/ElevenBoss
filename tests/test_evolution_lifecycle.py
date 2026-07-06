"""Evolution lifecycle helpers."""
from __future__ import annotations

from player_engine import EVOLUTION_TRACKS, VALID_TRACK_IDS, track_goal


def test_evolution_tracks_defined() -> None:
    assert len(EVOLUTION_TRACKS) == 3
    assert VALID_TRACK_IDS == frozenset({"pace_boost", "shooting_star", "def_wall"})
    assert track_goal("pace_boost") == 3


def test_track_has_legacy_goal_alias() -> None:
    for track in EVOLUTION_TRACKS.values():
        assert track["goal"] == track["matches_required"]
