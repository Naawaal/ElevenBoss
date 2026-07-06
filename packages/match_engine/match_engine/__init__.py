# packages/match_engine/match_engine/__init__.py
from __future__ import annotations

from .models import MatchPlayerCard, MatchInput, MatchResult, EventType, MatchEvent
from .simulator import simulate_match
from .commentary import generate_match_script
from .commentary_engine import CommentaryEngine, render_commentary, bold_vars
from .v2_simulator import MatchState, stream_match, collect_match_events
from .fixture_generator import generate_round_robin_fixtures, expected_fixture_counts
from .formation_positions import get_coordinates_for_formation, FORMATION_COORDINATES, get_slot_role

__all__ = [
    "MatchPlayerCard",
    "MatchInput",
    "MatchResult",
    "simulate_match",
    "EventType",
    "MatchEvent",
    "generate_match_script",
    "CommentaryEngine",
    "render_commentary",
    "bold_vars",
    "MatchState",
    "stream_match",
    "collect_match_events",
    "generate_round_robin_fixtures",
    "expected_fixture_counts",
    "get_coordinates_for_formation",
    "FORMATION_COORDINATES",
    "get_slot_role",
]
