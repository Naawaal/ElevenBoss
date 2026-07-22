# packages/match_engine/match_engine/v3/context.py
"""Immutable MatchContext + step result types for NSS v3."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from match_engine.models import MatchPlayerCard

from .possession import Possession


class ReplayMeta(BaseModel):
    schema_version: int = 1
    engine_version: str = "nss_v3"
    simulation_schema_version: int = 1
    rng_draw_count: int = 0
    seq_start: int = 0
    seq_end: int = 0


class DecisionContext(BaseModel):
    """Read-only view for human UI / Policy — never mutable squad refs."""

    minute: int = 0
    home_score: int = 0
    away_score: int = 0
    phase: str = "MIDFIELD"
    attacking_side: str = "home"
    own_tactic: str = "balanced"
    opponent_tactic: str = "balanced"
    legal_actions: list[str] = Field(default_factory=list)
    open_decision_window: int | None = None
    intensity_tier: int = 1
    trailing: bool = False
    last_events_summary: list[str] = Field(default_factory=list)


class MatchContext(BaseModel):
    """Immutable snapshot after each step (Phase 0)."""

    model_config = {"arbitrary_types_allowed": True}

    minute: int = 0
    home_score: int = 0
    away_score: int = 0
    phase: str = "MIDFIELD"
    attacking_side: str = "home"
    momentum_home: float = 0.0
    momentum_away: float = 0.0
    stagnation_home: int = 0
    stagnation_away: int = 0
    tactic_home: str = "balanced"
    tactic_away: str = "balanced"
    stance_modifier_home: float = 1.0
    stance_modifier_away: float = 1.0
    home_rating: float = 50.0
    away_rating: float = 50.0
    home_name: str = "Home"
    away_name: str = "Away"
    home_squad: list[MatchPlayerCard] = Field(default_factory=list)
    away_squad: list[MatchPlayerCard] = Field(default_factory=list)
    bench_home: list[Any] = Field(default_factory=list)
    bench_away: list[Any] = Field(default_factory=list)
    possession: Possession | None = None
    intensity_tier: int = 1
    injuries_enabled: bool = False
    interactive_sides: list[str] = Field(default_factory=list)
    engine_version: str = "nss_v3"
    simulation_schema_version: int = 1
    schema_version: int = 1
    rng_draw_count: int = 0
    next_seq: int = 1
    awaiting_decision: bool = False
    awaiting_reason: str | None = None
    terminal: bool = False
    weather: str | None = None  # unused Phase 0


class StepResult(BaseModel):
    events: list[Any] = Field(default_factory=list)
    context: MatchContext
    elapsed_minutes: int = 0
    terminal: bool = False
    awaiting_decision: bool = False
    legal_actions: list[str] = Field(default_factory=list)
    possession_ended: bool = False
    replay_meta: ReplayMeta = Field(default_factory=ReplayMeta)
