# packages/gacha/gacha/__init__.py
from __future__ import annotations

from .generator import generate_pack, generate_starter_squad, generate_support_legendary, generate_youth_intake
from .models import GachaPack, GachaPlayer, RARITY_RATING_RANGES, StarterSquad
from .pack_configs import (
    PACKS,
    PackConfig,
    UnknownPackConfigError,
    get_pack_config,
    resolve_pack_config,
    sanitize_pack_config,
)

__all__ = [
    "GachaPlayer",
    "GachaPack",
    "StarterSquad",
    "RARITY_RATING_RANGES",
    "PackConfig",
    "PACKS",
    "UnknownPackConfigError",
    "get_pack_config",
    "resolve_pack_config",
    "sanitize_pack_config",
    "generate_pack",
    "generate_starter_squad",
    "generate_support_legendary",
    "generate_youth_intake",
]
