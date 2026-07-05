# packages/player_engine/player_engine/config.py
from __future__ import annotations
from pydantic import BaseModel

class GameConfig(BaseModel):
    xp_per_match_base: int = 15
    age_modifier_youth: float = 1.15
    level_curve_base: float = 100.0
    level_curve_exponent: float = 1.12
