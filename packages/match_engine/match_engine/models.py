# packages/match_engine/match_engine/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

class MatchPlayerCard(BaseModel):
    name: str
    position: str
    overall: int = Field(..., ge=1)

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
