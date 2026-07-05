# packages/leagues/leagues/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

class LeagueEntry(BaseModel):
    discord_id: int
    league_points: int = Field(default=0, ge=0)
    goal_difference: int = Field(default=0)

class PromotionResult(BaseModel):
    promoted_ids: list[int]
    relegated_ids: list[int]
    retained_ids: list[int]
