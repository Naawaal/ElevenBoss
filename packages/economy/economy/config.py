# packages/economy/economy/config.py
from __future__ import annotations
from pydantic import BaseModel, Field

class GameConfig(BaseModel):
    wage_scale_factor: float = 1.2
    xp_base_per_hour: float = 10.0
    drill_durations: dict[str, float] = Field(
        default_factory=lambda: {
            "cardio": 1.0,
            "tactics": 4.0,
            "match_prep": 8.0
        }
    )
    # Coin costs for starting drills
    drill_costs: dict[str, int] = Field(
        default_factory=lambda: {
            "cardio": 50,
            "tactics": 150,
            "match_prep": 250
        }
    )
    # Base XP gained from completing drills
    drill_xp: dict[str, int] = Field(
        default_factory=lambda: {
            "cardio": 20,
            "tactics": 100,
            "match_prep": 250
        }
    )
