# packages/gacha/gacha/__init__.py
from __future__ import annotations

from .generator import (
    MANAGER_CARD_GIFTS_CAMPAIGN,
    generate_manager_gift_epic,
    generate_manager_gift_legendary_mid,
    generate_pack,
    generate_starter_squad,
    generate_support_legendary,
    generate_youth_intake,
    manager_gift_rng,
)
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
    "MANAGER_CARD_GIFTS_CAMPAIGN",
    "generate_pack",
    "generate_starter_squad",
    "generate_support_legendary",
    "generate_manager_gift_epic",
    "generate_manager_gift_legendary_mid",
    "manager_gift_rng",
    "generate_youth_intake",
]
