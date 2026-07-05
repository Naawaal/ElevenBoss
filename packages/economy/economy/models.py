# packages/economy/economy/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

class LevelUpResult(BaseModel):
    new_level: int = Field(..., ge=1)
    new_overall: int = Field(..., ge=1)
    cost: int = Field(..., ge=0)
