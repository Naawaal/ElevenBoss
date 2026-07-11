# packages/player_engine/player_engine/injury_math.py
"""Post-match injury chance, tiers, hospital recovery (A+C soft-cap)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence

INJURY_ELIGIBLE_FATIGUE_BELOW = 75  # soft-cap C
INJURY_BASE_CHANCE = 0.004  # 0.4%

TIER_MINOR = 1
TIER_MODERATE = 2
TIER_MAJOR = 3

TIER_NAMES = {1: "Minor", 2: "Moderate", 3: "Major"}
BASE_RECOVERY_DAYS = {1: 3, 2: 8, 3: 20}


@dataclass(frozen=True)
class InjuryRollResult:
    player_card_id: str
    tier: int
    chance: float


def injury_chance(fatigue: int, age: int, phy: int) -> float:
    """Per-player injury probability (before A+C filters)."""
    fat_mod = (100 - fatigue) * 0.0004
    age_mod = max(0, (age - 30) * 0.0015)
    phy_mod = max(0, (phy - 70) * -0.0002)
    return max(0.0, INJURY_BASE_CHANCE + fat_mod + age_mod + phy_mod)


def roll_injury_tier(rng: random.Random | None = None) -> int:
    """1–60 Minor, 61–90 Moderate, 91–100 Major (no career-ending)."""
    r = (rng or random).randint(1, 100)
    if r <= 60:
        return TIER_MINOR
    if r <= 90:
        return TIER_MODERATE
    return TIER_MAJOR


def hospital_bed_capacity(hospital_level: int) -> int:
    return max(0, int(hospital_level)) + 1


def hospital_recovery_multiplier(hospital_level: int) -> float:
    return 1.0 / (1.0 + 0.2 * max(0, int(hospital_level)))


def recovery_days_for_tier(tier: int, hospital_level: int) -> int:
    base = BASE_RECOVERY_DAYS.get(tier, 8)
    days = base / (1.0 + 0.2 * max(0, int(hospital_level)))
    return max(1, int(__import__("math").ceil(days)))


def select_post_match_injury(
    starters: Sequence[dict[str, Any]],
    *,
    rng: random.Random | None = None,
) -> InjuryRollResult | None:
    """
    A+C soft-cap:
    - Only starters with fatigue < 75 are eligible (C).
    - At most one injury per club: first successful roll in starter order (A).
    """
    r = rng or random.Random()
    for card in starters:
        fatigue = int(card.get("fatigue", 100))
        if fatigue >= INJURY_ELIGIBLE_FATIGUE_BELOW:
            continue
        card_id = str(card.get("id") or card.get("player_card_id") or "")
        if not card_id:
            continue
        age = int(card.get("age") or 25)
        phy = int(card.get("phy", 50))
        chance = injury_chance(fatigue, age, phy)
        if r.random() < chance:
            return InjuryRollResult(
                player_card_id=card_id,
                tier=roll_injury_tier(r),
                chance=chance,
            )
    return None
