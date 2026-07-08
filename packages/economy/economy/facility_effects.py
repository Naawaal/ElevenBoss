# packages/economy/economy/facility_effects.py
"""Club facility upgrade costs and gameplay effects (Phase C)."""
from __future__ import annotations

from dataclasses import dataclass

FACILITY_UPGRADE_COSTS: tuple[int, ...] = (750, 2000, 5000, 12000)
FACILITY_MAX_LEVEL: int = 5
FACILITY_WEEKLY_CAP_DAYS: int = 7

# Target level -> minimum career matches required before upgrading TO that level
FACILITY_MIN_MATCHES: dict[int, int] = {2: 5, 4: 20}


@dataclass(frozen=True)
class YouthAcademyTier:
    level: int
    pot_min: int
    pot_max: int
    ovr_min: int
    ovr_max: int
    gem_chance: float


YOUTH_ACADEMY_TIERS: dict[int, YouthAcademyTier] = {
    1: YouthAcademyTier(1, 72, 82, 50, 65, 0.0),
    2: YouthAcademyTier(2, 72, 85, 52, 66, 0.05),
    3: YouthAcademyTier(3, 72, 88, 54, 67, 0.10),
    4: YouthAcademyTier(4, 72, 91, 55, 68, 0.15),
    5: YouthAcademyTier(5, 72, 94, 56, 69, 0.20),
}


def facility_upgrade_cost(current_level: int) -> int | None:
    """Coin cost to upgrade from current_level to current_level + 1."""
    if current_level < 1 or current_level >= FACILITY_MAX_LEVEL:
        return None
    return FACILITY_UPGRADE_COSTS[current_level - 1]


def training_ground_drill_xp_bonus(training_ground_level: int) -> int:
    """Flat drill XP bonus: L1 +0 … L5 +4."""
    level = max(1, min(FACILITY_MAX_LEVEL, training_ground_level))
    return level - 1


def youth_academy_tier(academy_level: int) -> YouthAcademyTier:
    level = max(1, min(FACILITY_MAX_LEVEL, academy_level))
    return YOUTH_ACADEMY_TIERS[level]


def min_matches_for_next_level(current_level: int) -> int:
    """Matches required to upgrade to current_level + 1 (0 if none)."""
    return FACILITY_MIN_MATCHES.get(current_level + 1, 0)


def facility_label(facility_key: str) -> str:
    return {
        "youth_academy": "Youth Academy",
        "training_ground": "Training Ground",
    }.get(facility_key, facility_key)
