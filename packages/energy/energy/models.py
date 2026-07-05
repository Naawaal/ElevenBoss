# packages/energy/energy/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

class EnergyStatus(BaseModel):
    current_energy: int = Field(..., ge=0)
    max_energy: int = Field(default=100, gt=0)
