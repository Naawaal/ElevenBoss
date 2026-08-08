# packages/match_engine/match_engine/competitive_models.py
"""Competitive Bot Match phase models and deterministic seeds (Feature 057)."""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MatchPhase(str, Enum):
    REGULATION = "REGULATION"
    EXTRA_TIME_FIRST = "EXTRA_TIME_FIRST"
    EXTRA_TIME_SECOND = "EXTRA_TIME_SECOND"
    PENALTY_SHOOTOUT = "PENALTY_SHOOTOUT"
    COMPLETE = "COMPLETE"


class DecidedBy(str, Enum):
    REGULATION = "regulation"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"


class PenaltyKickEvent(BaseModel):
    sequence: int
    club_side: str  # "home" | "away"
    player_id: str
    player_name: str
    goalkeeper_id: str
    goalkeeper_name: str
    outcome: str  # goal | saved | missed
    seed_key: str


class PenaltyShootoutState(BaseModel):
    home_kicks_taken: int = 0
    away_kicks_taken: int = 0
    home_penalties_scored: int = 0
    away_penalties_scored: int = 0
    home_taker_order: list[str] = Field(default_factory=list)
    away_taker_order: list[str] = Field(default_factory=list)
    home_taker_names: dict[str, str] = Field(default_factory=dict)
    away_taker_names: dict[str, str] = Field(default_factory=dict)
    home_taker_index: int = 0
    away_taker_index: int = 0
    sudden_death: bool = False
    completed: bool = False
    winner_side: str | None = None
    events: list[PenaltyKickEvent] = Field(default_factory=list)

    def to_persist(self) -> dict[str, Any]:
        return self.model_dump()


def deterministic_sub_seed(sim_seed: int, label: str) -> int:
    """Derive a stable 63-bit seed from match seed + phase label."""
    raw = f"{int(sim_seed)}:{label}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:16], 16) & 0x7FFFFFFFFFFFFFFF


def competitive_snapshot(
    *,
    phase: MatchPhase | str,
    phase_minute: int,
    home_score: int,
    away_score: int,
    decided_by: str | None = None,
    penalty_state: dict[str, Any] | None = None,
    home_penalties: int = 0,
    away_penalties: int = 0,
    et1_seed: int | None = None,
    et2_seed: int | None = None,
    shootout_seed: int | None = None,
) -> dict[str, Any]:
    return {
        "match_phase": phase.value if isinstance(phase, MatchPhase) else str(phase),
        "phase_minute": int(phase_minute),
        "home_score": int(home_score),
        "away_score": int(away_score),
        "decided_by": decided_by,
        "penalty_state": penalty_state,
        "home_penalties": int(home_penalties),
        "away_penalties": int(away_penalties),
        "et1_seed": et1_seed,
        "et2_seed": et2_seed,
        "shootout_seed": shootout_seed,
    }
