# packages/match_engine/match_engine/__init__.py
from __future__ import annotations

from .models import MatchPlayerCard, MatchInput, MatchResult, EventType, MatchEvent
from .simulator import simulate_match
from .commentary import generate_match_script
from .commentary_engine import CommentaryEngine
from .v2_simulator import MatchState, stream_match
from .fixture_generator import generate_round_robin_fixtures, expected_fixture_counts

__all__ = [
    "MatchPlayerCard",
    "MatchInput",
    "MatchResult",
    "simulate_match",
    "EventType",
    "MatchEvent",
    "generate_match_script",
    "CommentaryEngine",
    "MatchState",
    "stream_match",
    "generate_round_robin_fixtures",
    "expected_fixture_counts",
]
