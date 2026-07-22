# packages/match_engine/match_engine/v3/__init__.py
from __future__ import annotations

from .adapters import collect_match_events_v3, stream_match_v3
from .brain import BotBrain, DefaultPolicy, Policy
from .context import DecisionContext, MatchContext, ReplayMeta, StepResult
from .decisions import (
    DECISION_WINDOWS,
    DecisionInbox,
    DecisionIntent,
    intents_from_decision_events,
)
from .digests import (
    deterministic_replay_digest,
    settlement_digest,
    sporting_digest,
)
from .engine import ENGINE_VERSION, SIMULATION_SCHEMA_VERSION, SimulationEngine
from .events import EventCategory, MatchEventV3, from_compat_dict
from .policies import AggressivePolicy, DefensivePolicy
from .possession import Possession, PossessionTracker
from .projectors import (
    BoxScore,
    Explanation,
    ReplayTimeline,
    project_box_score,
    project_explanation,
    project_replay_timeline,
)
from .tactics import TransitionProfile, get_transition_profile

__all__ = [
    "BotBrain",
    "DefaultPolicy",
    "Policy",
    "AggressivePolicy",
    "DefensivePolicy",
    "DecisionContext",
    "MatchContext",
    "ReplayMeta",
    "StepResult",
    "DECISION_WINDOWS",
    "DecisionInbox",
    "DecisionIntent",
    "intents_from_decision_events",
    "deterministic_replay_digest",
    "settlement_digest",
    "sporting_digest",
    "ENGINE_VERSION",
    "SIMULATION_SCHEMA_VERSION",
    "SimulationEngine",
    "EventCategory",
    "MatchEventV3",
    "from_compat_dict",
    "Possession",
    "PossessionTracker",
    "BoxScore",
    "Explanation",
    "ReplayTimeline",
    "project_box_score",
    "project_explanation",
    "project_replay_timeline",
    "stream_match_v3",
    "collect_match_events_v3",
    "TransitionProfile",
    "get_transition_profile",
]
