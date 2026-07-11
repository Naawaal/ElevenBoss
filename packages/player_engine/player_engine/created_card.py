# packages/player_engine/player_engine/created_card.py
"""Typed factory output for procedural player creation."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CreatedPlayerCard(BaseModel):
    """Validated card contract from create_player_card (package boundary)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    position: str = Field(..., pattern="^(GK|DEF|MID|FWD)$")
    rarity: str = Field(..., pattern="^(Common|Rare|Epic|Legendary)$")
    role: str = Field(..., min_length=1)
    base_rating: int = Field(..., ge=1, le=99)
    overall: int = Field(..., ge=1, le=99)
    pac: int = Field(..., ge=10, le=99)
    sho: int = Field(..., ge=10, le=99)
    pas: int = Field(..., ge=10, le=99)
    dri: int = Field(..., ge=10, le=99)
    def_stat: int = Field(..., alias="def", ge=10, le=99)
    phy: int = Field(..., ge=10, le=99)
    potential: int = Field(..., ge=1, le=99)
    base_potential: int = Field(..., ge=1, le=99)
    age: int = Field(..., ge=15, le=45)
    date_of_birth: str
    source_card_id: str | None = None
