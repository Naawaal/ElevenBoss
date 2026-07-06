# packages/gacha/gacha/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

RARITY_RATING_RANGES: dict[str, tuple[int, int]] = {
    "Common": (50, 64),
    "Rare": (65, 74),
    "Epic": (75, 84),
    "Legendary": (85, 99),
}

class GachaPlayer(BaseModel):
    name: str
    position: str = Field(..., pattern="^(GK|DEF|MID|FWD)$")
    rarity: str = Field(..., pattern="^(Common|Rare|Epic|Legendary)$")
    base_rating: int = Field(..., ge=50, le=99)
    overall: int = Field(..., ge=50, le=99)
    pac: int = Field(50, ge=0, le=99)
    sho: int = Field(50, ge=0, le=99)
    pas: int = Field(50, ge=0, le=99)
    dri: int = Field(50, ge=0, le=99)
    def_stat: int = Field(50, alias="def", ge=0, le=99)
    phy: int = Field(50, ge=0, le=99)
    potential: int = Field(..., ge=1, le=99)
    age: int = Field(25, ge=15, le=45)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class GachaPack(BaseModel):
    players: list[GachaPlayer]

class StarterSquad(BaseModel):
    marquee: GachaPlayer
    youth: list[GachaPlayer]

    @property
    def all_players(self) -> list[GachaPlayer]:
        """Full 11-player list: [marquee] + youth, ordered GK -> DEF -> MID -> FWD."""
        ordered = sorted(
            [self.marquee] + self.youth,
            key=lambda p: ["GK", "DEF", "MID", "FWD"].index(p.position)
        )
        return ordered
