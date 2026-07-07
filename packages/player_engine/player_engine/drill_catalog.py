# packages/player_engine/player_engine/drill_catalog.py
"""Stat drill tiers and level gates — single source of truth (US-23)."""
from __future__ import annotations

from dataclasses import dataclass

DRILL_TIERS: dict[str, dict] = {
    "basic": {"min_level": 1, "energy": 15, "coin_ovr_mult": 5, "xp_base": 25},
    "intermediate": {"min_level": 10, "energy": 20, "coin_ovr_mult": 8, "xp_base": 60},
    "advanced": {"min_level": 25, "energy": 25, "coin_ovr_mult": 12, "xp_base": 120},
    "elite": {"min_level": 50, "energy": 30, "coin_ovr_mult": 15, "xp_base": 200},
}

STAT_DRILLS: dict[str, dict] = {
    "pac_sprint": {"name": "⚡ Pace Sprint", "tier": "basic", "stat": "pac"},
    "sho_finishing": {"name": "🎯 Finishing Drill", "tier": "basic", "stat": "sho"},
    "pas_distribution": {"name": "🧠 Distribution Drill", "tier": "basic", "stat": "pas"},
    "dri_dribble": {"name": "👟 Dribbling Drill", "tier": "basic", "stat": "dri"},
    "def_tackling": {"name": "🛡️ Tackling Drill", "tier": "basic", "stat": "def"},
    "phy_strength": {"name": "💪 Strength Drill", "tier": "basic", "stat": "phy"},
}

VALID_DRILL_IDS = frozenset(STAT_DRILLS.keys())


@dataclass(frozen=True)
class DrillSpec:
    drill_id: str
    name: str
    tier: str
    stat: str
    min_level: int
    energy: int
    coin_ovr_mult: int
    xp_base: int


def drill_spec(drill_id: str) -> DrillSpec | None:
    meta = STAT_DRILLS.get(drill_id)
    if not meta:
        return None
    tier = DRILL_TIERS[meta["tier"]]
    return DrillSpec(
        drill_id=drill_id,
        name=meta["name"],
        tier=meta["tier"],
        stat=meta["stat"],
        min_level=tier["min_level"],
        energy=tier["energy"],
        coin_ovr_mult=tier["coin_ovr_mult"],
        xp_base=tier["xp_base"],
    )


def drill_unlocked(drill_id: str, player_level: int) -> bool:
    spec = drill_spec(drill_id)
    return spec is not None and player_level >= spec.min_level


def drill_coin_cost(drill_id: str, ovr: int) -> int:
    spec = drill_spec(drill_id)
    if not spec:
        return 0
    return spec.coin_ovr_mult * max(0, ovr)
