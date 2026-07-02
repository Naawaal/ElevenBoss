# app/engine/tactics.py
"""
Tactics system for the interval-based simulation loop (Milestone D).

Design rules (engine purity):
  - No imports from app.models, app.db, app.services, or Discord.
  - All multiplier values are sourced from MatchEngineConfig, never hardcoded here.
  - TacticProfile is frozen and stateless — same tactic always yields the same modifiers.

Multiplier stacking order (enforced in _compute_interval_xg in match_engine.py):
  base_strength × suitability × fitness × home_boost × tactic_mult × momentum_mult → clamp
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.match_config import MatchEngineConfig


class TacticType(str, Enum):
    """
    The five supported match tactics. Defaults to BALANCED when not specified.

    BALANCED      — neutral modifiers; the pre-Milestone-D baseline.
    HIGH_PRESS    — attacks hard and wins midfield but drains fitness faster and fouls more.
    POSSESSION    — controls midfield at the cost of reduced direct attacking output.
    COUNTER_ATTACK— sacrifices attack/midfield in-press for a defensive shape and pace transitions.
    PARK_THE_BUS  — extreme defensive, very low attack output, minimal fatigue.
    """
    BALANCED       = "balanced"
    HIGH_PRESS     = "high_press"
    POSSESSION     = "possession"
    COUNTER_ATTACK = "counter_attack"
    PARK_THE_BUS   = "park_the_bus"


@dataclass(frozen=True)
class TacticProfile:
    """
    Per-interval strength multipliers and rate modifiers for a given tactic.

    Fields:
        attack_mult:     Multiplier on the attacking team's attack strength.
        defense_mult:    Multiplier on the attacking team's defensive strength.
        midfield_mult:   Multiplier on the attacking team's midfield strength.
        foul_prob_mult:  Scales per-interval yellow card rates (>1.0 = more fouls).
        fatigue_mult:    Scales fitness_decay_per_interval (HIGH_PRESS > 1.0 = tires faster).

    All values are applied per interval, not per match. Sourced from MatchEngineConfig
    to keep them tunable without code changes.
    """
    attack_mult:    float
    defense_mult:   float
    midfield_mult:  float
    foul_prob_mult: float
    fatigue_mult:   float


def get_tactic_profile(tactic: TacticType, config: MatchEngineConfig) -> TacticProfile:
    """
    Return the TacticProfile for the given TacticType, using values from config.

    Config fields used (all prefixed with tactic_<name>_):
        attack_mult, defense_mult, midfield_mult, foul_prob_mult, fatigue_mult
    """
    prefix = f"tactic_{tactic.value}_"
    return TacticProfile(
        attack_mult=getattr(config, prefix + "attack_mult"),
        defense_mult=getattr(config, prefix + "defense_mult"),
        midfield_mult=getattr(config, prefix + "midfield_mult"),
        foul_prob_mult=getattr(config, prefix + "foul_prob_mult"),
        fatigue_mult=getattr(config, prefix + "fatigue_mult"),
    )
