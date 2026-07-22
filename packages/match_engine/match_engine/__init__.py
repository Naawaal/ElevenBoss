# packages/match_engine/match_engine/__init__.py
from __future__ import annotations

from .models import MatchPlayerCard, MatchInput, MatchResult, EventType, MatchEvent
from .simulator import simulate_match
from .commentary import generate_match_script
from .commentary_engine import CommentaryEngine, render_commentary, bold_vars
from .v2_simulator import MatchState, stream_match, collect_match_events
from .match_stats import MatchLiveStats, stats_from_events, zone_averages, format_zone_breakdown
from .fixture_generator import generate_round_robin_fixtures, expected_fixture_counts
from .formation_positions import get_coordinates_for_formation, FORMATION_COORDINATES, get_slot_role
from .squad_validation import reassign_formation_slots, reserve_fits_formation_slot
from .substitution_resolve import (
    SubResolution,
    auto_pick_bench,
    auto_resolve_injury,
    play_on_tier_upgrade,
    MAX_SUBS_PER_MATCH,
)
from .bot_squad import build_bot_match_squad
from .v2_simulator import generate_match_events
from .v3 import (
    ENGINE_VERSION as NSS_V3_ENGINE_VERSION,
    SIMULATION_SCHEMA_VERSION,
    SimulationEngine,
    DecisionInbox,
    DecisionIntent,
    MatchContext,
    MatchEventV3,
    sporting_digest,
    deterministic_replay_digest,
    settlement_digest,
    stream_match_v3,
    collect_match_events_v3,
)

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
    "generate_match_events",
    "generate_round_robin_fixtures",
    "expected_fixture_counts",
    "get_coordinates_for_formation",
    "FORMATION_COORDINATES",
    "get_slot_role",
    "reserve_fits_formation_slot",
    "reassign_formation_slots",
    "MatchLiveStats",
    "stats_from_events",
    "zone_averages",
    "format_zone_breakdown",
    "SubResolution",
    "auto_pick_bench",
    "auto_resolve_injury",
    "play_on_tier_upgrade",
    "MAX_SUBS_PER_MATCH",
    "build_bot_match_squad",
    "NSS_V3_ENGINE_VERSION",
    "SIMULATION_SCHEMA_VERSION",
    "SimulationEngine",
    "DecisionInbox",
    "DecisionIntent",
    "MatchContext",
    "MatchEventV3",
    "sporting_digest",
    "deterministic_replay_digest",
    "settlement_digest",
    "stream_match_v3",
    "collect_match_events_v3",
]
