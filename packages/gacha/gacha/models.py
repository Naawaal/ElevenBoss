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
