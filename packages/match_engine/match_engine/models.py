# packages/match_engine/match_engine/models.py
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class EventType(str, Enum):
    KICKOFF = "KICKOFF"
    HALF_TIME = "HALF_TIME"
    GOAL = "GOAL"
    MISS = "MISS"
    SAVE = "SAVE"
    YELLOW_CARD = "YELLOW_CARD"
    FULL_TIME = "FULL_TIME"
    CHANCE = "CHANCE"
    FOUL = "FOUL"
    INJURY = "INJURY"

class MatchPlayerCard(BaseModel):
    name: str
    position: str
    overall: int = Field(..., ge=1)
    pac: int = 50
    sho: int = 50
    pas: int = 50
    dri: int = 50
    def_stat: int = Field(50, alias="def")
    phy: int = 50
    morale: int = 80
    fatigue: int = 100
    card_id: str | None = None
    playstyles: list[str] = Field(default_factory=list)
    compromised: bool = False  # Play On — phase attr ×0.50
    emergency_gk: bool = False  # outfield pressed into GK

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class MatchInput(BaseModel):
    my_players: list[MatchPlayerCard]
    opponent_base_rating: float = Field(..., ge=1.0)

class MatchResult(BaseModel):
    result: str = Field(..., pattern="^(win|draw|loss)$")
    goals_for: int = Field(..., ge=0)
    goals_against: int = Field(..., ge=0)
    my_rating: float = Field(..., ge=0.0)
    opponent_rating: float = Field(..., ge=0.0)
    coins_earned: int = Field(..., ge=0)
    points_earned: int = Field(..., ge=0)
    possession_home: int = 50
    possession_away: int = 50
    shots_home: int = 10
    shots_away: int = 10
    motm: str = "TBD"
    key_events: list[dict] = Field(default_factory=list)

class MatchEvent(BaseModel):
    minute: int = Field(..., ge=0, le=90)
    type: EventType
    text: str
    score_update: Optional[str] = None
