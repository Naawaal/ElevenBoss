# app/engine/momentum.py
"""
Momentum / game-state feedback system for the interval-based simulation loop (Milestone E).

Design rules (engine purity):
  - No imports from app.models, app.db, app.services, or Discord.
  - compute_momentum() is a pure function — reads state, returns a modifier, mutates nothing.
  - Momentum represents which team has the psychological/tactical edge at a given moment.
    It is driven by the score differential and recent goal scoring, NOT cumulative match stats.

Multiplier stacking order (enforced in _compute_interval_xg in match_engine.py):
  base_strength × suitability × fitness × home_boost × tactic_mult × momentum_mult → clamp
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.match_config import MatchEngineConfig
    from app.engine.match_state import MatchState
    from app.engine.match_engine import MatchGoalEvent


@dataclass(frozen=True)
class MomentumModifier:
    """
    Per-interval attack and defense multipliers derived from current match momentum.

    Fields:
        home_attack_mult:  Applied to home team's attack strength this interval.
        home_defense_mult: Applied to home team's defense strength this interval.
        away_attack_mult:  Applied to away team's attack strength this interval.
        away_defense_mult: Applied to away team's defense strength this interval.

    Neutral (no momentum effect) is all fields = 1.0.
    """
    home_attack_mult:  float = 1.0
    home_defense_mult: float = 1.0
    away_attack_mult:  float = 1.0
    away_defense_mult: float = 1.0


def compute_momentum(
    state: MatchState,
    interval_index: int,
    config: MatchEngineConfig,
    home_club_id: str = "",
) -> MomentumModifier:
    """
    Compute the momentum modifier for the current interval.

    Momentum is driven by two factors:
      1. Goal difference (state.home_score - state.away_score): the leading team gains
         a sustained but decaying confidence boost.
      2. Recency of last goal: scoring in the previous interval yields a short spike
         (the "just scored" momentum burst) that decays after one interval.

    Args:
        state:          Current MatchState (score and event log are read; nothing mutated).
        interval_index: 0-based index of the current interval (0..interval_count-1).
        config:         MatchEngineConfig with momentum_* fields.
        home_club_id:   The home team's club_id, used to attribute recency goals correctly.
                        Defaults to "" (recency detection disabled when not provided).

    Returns:
        MomentumModifier with home/away attack and defense multipliers for this interval.
        All multipliers are clamped to [1/max_mult, max_mult].
    """
    goal_diff = state.home_score - state.away_score

    # Red card disadvantage: each extra red card suffered penalises momentum as if
    # the team were additionally down by momentum_red_card_weight goals.
    # home_red_cards > away_red_cards → home is a man down → reduce home momentum.
    red_card_diff = state.home_red_cards - state.away_red_cards
    effective_diff = goal_diff - (red_card_diff * config.momentum_red_card_weight)

    # --- Recency bonus: did either team score in the immediately previous interval? ---
    prev_interval_start = (interval_index - 1) * config.interval_length_minutes + 1
    prev_interval_end   = interval_index * config.interval_length_minutes

    home_just_scored = False
    away_just_scored = False
    if interval_index > 0 and home_club_id:
        for event in state.events:
            # MatchGoalEvent has a club_id; check if it falls in the previous interval
            if hasattr(event, "scorer_id"):  # MatchGoalEvent check (engine-pure duck-typing)
                if prev_interval_start <= event.minute <= prev_interval_end:
                    if event.club_id == home_club_id:
                        home_just_scored = True
                    else:
                        away_just_scored = True

    # --- Score-differential momentum (including red card penalty) ---
    capped_diff = max(-config.momentum_goal_cap, min(config.momentum_goal_cap, effective_diff))
    base_boost = capped_diff * config.momentum_goal_boost

    # --- Recency spike ---
    recency_home = config.momentum_recency_boost if home_just_scored else 0.0
    recency_away = config.momentum_recency_boost if away_just_scored else 0.0

    # Home: up when leading + just scored; down when trailing
    home_advantage = base_boost + recency_home
    away_advantage = -base_boost + recency_away

    # Convert to multipliers: positive advantage → attack boost + defensive resilience
    home_atk = 1.0 + home_advantage * config.momentum_attack_weight
    home_def = 1.0 + home_advantage * config.momentum_defense_weight
    away_atk = 1.0 + away_advantage * config.momentum_attack_weight
    away_def = 1.0 + away_advantage * config.momentum_defense_weight

    # Clamp each to [1/max_mult, max_mult] before returning
    mx = config.momentum_max_mult
    mn = 1.0 / mx

    return MomentumModifier(
        home_attack_mult=max(mn, min(mx, home_atk)),
        home_defense_mult=max(mn, min(mx, home_def)),
        away_attack_mult=max(mn, min(mx, away_atk)),
        away_defense_mult=max(mn, min(mx, away_def)),
    )
