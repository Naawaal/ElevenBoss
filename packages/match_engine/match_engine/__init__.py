# packages/match_engine/match_engine/__init__.py
from __future__ import annotations

from .models import MatchPlayerCard, MatchInput, MatchResult, EventType, MatchEvent
from .simulator import simulate_match
from .commentary import generate_match_script

__all__ = [
    "MatchPlayerCard",
    "MatchInput",
    "MatchResult",
    "simulate_match",
    "EventType",
    "MatchEvent",
    "generate_match_script",
]
