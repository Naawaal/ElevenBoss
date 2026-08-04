# packages/pvp/pvp/models.py
"""Pydantic models for Ranked PvP matchmaking and rivalries (Feature 053)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QueueStatus = Literal["searching", "matching", "matched", "cancelled", "expired"]
RivalryStatus = Literal["tracking", "active", "dormant"]
MatchMode = Literal["pvp", "practice", "friendly", "league", "bot"]
MatchResult = Literal["win", "draw", "loss"]


class QueueCandidate(BaseModel):
    """Snapshot of a manager searching for Ranked PvP."""

    owner_id: int
    guild_id: int
    channel_id: int = 0
    global_division: str
    division_rank: int = Field(
        ge=0,
        description="Ordinal rank for widening (0 = lowest tier). Same value = same division.",
    )
    global_lp: int = Field(ge=0)
    xi_rating: float
    joined_at: datetime
    queue_id: str | None = None


class SearchRange(BaseModel):
    """Allowed skill band at a given queue age."""

    max_division_delta: int = Field(ge=0)
    max_lp_delta: int = Field(ge=0)
    max_ovr_delta: float = Field(ge=0)


class PairScore(BaseModel):
    """Lower is better — used to pick among eligible pairs."""

    wait_seconds: float
    division_delta: int
    lp_delta: int
    ovr_delta: float

    def sort_key(self) -> tuple[float, int, int, float]:
        # Longest wait first ⇒ negate wait for ascending sort
        return (-self.wait_seconds, self.division_delta, self.lp_delta, self.ovr_delta)


class RivalryEvent(BaseModel):
    code: str
    message: str


class RivalryState(BaseModel):
    manager_a_id: int
    manager_b_id: int
    meetings: int = 0
    a_wins: int = 0
    b_wins: int = 0
    draws: int = 0
    a_goals: int = 0
    b_goals: int = 0
    current_streak_owner: int | None = None
    current_streak_count: int = 0
    longest_streak_owner: int | None = None
    longest_streak_count: int = 0
    last_winner_id: int | None = None
    status: RivalryStatus = "tracking"
    activated_at: datetime | None = None
    last_match_at: datetime | None = None
    first_meeting_in_window_at: datetime | None = None


class RewardPolicyResult(BaseModel):
    match_mode: MatchMode
    energy_cost: int
    coin_multiplier: float
    xp_multiplier: float
    global_lp_delta: int
    rivalry_counted: bool
    updates_pvp_record: bool
