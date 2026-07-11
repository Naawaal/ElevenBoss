# packages/gacha/gacha/pack_configs.py
"""Named pack product rules (rarity / position mixes)."""
from __future__ import annotations

from dataclasses import dataclass


class UnknownPackConfigError(ValueError):
    """Raised when generate_pack / get_pack_config receives an unknown pack id."""


@dataclass(frozen=True)
class PackConfig:
    id: str
    card_count: int
    rarities: tuple[str, ...]
    rarity_weights: tuple[int, ...]
    positions: tuple[str, ...]
    position_weights: tuple[int, ...]


PACKS: dict[str, PackConfig] = {
    "standard": PackConfig(
        id="standard",
        card_count=5,
        rarities=("Common", "Rare", "Epic", "Legendary"),
        rarity_weights=(60, 30, 8, 2),
        positions=("GK", "DEF", "MID", "FWD"),
        position_weights=(10, 30, 30, 30),
    ),
}


def get_pack_config(pack_id: str) -> PackConfig:
    cfg = PACKS.get(pack_id)
    if cfg is None:
        raise UnknownPackConfigError(f"Unknown pack config id: {pack_id!r}")
    return cfg
