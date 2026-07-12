# packages/player_engine/player_engine/injury_math.py
"""Post-match injury chance, tiers, hospital recovery (A+C soft-cap)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence

INJURY_ELIGIBLE_FATIGUE_BELOW = 75  # soft-cap C
INJURY_BASE_CHANCE = 0.004  # 0.4%

TIER_MINOR = 1
TIER_MODERATE = 2
TIER_MAJOR = 3

TIER_NAMES = {1: "Minor", 2: "Moderate", 3: "Major"}
BASE_RECOVERY_DAYS = {1: 1, 2: 4, 3: 7}


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
    base = BASE_RECOVERY_DAYS.get(tier, 4)
    days = base / (1.0 + 0.2 * max(0, int(hospital_level)))
    return max(1, int(math.ceil(days)))


def new_total_recovery_days(tier: int, hospital_level: int) -> int:
    """CEIL(base / (1 + 0.2 * H)); alias of recovery_days_for_tier for backfill clarity."""
    return recovery_days_for_tier(tier, hospital_level)


def fair_hospital_candidate_eta(
    *,
    admission: datetime,
    tier: int,
    hospital_level: int,
) -> datetime:
    """admission + new_total_recovery_days (calendar days)."""
    return admission + timedelta(days=new_total_recovery_days(tier, hospital_level))


def fair_hospital_final_eta(
    *,
    admission: datetime,
    current_eta: datetime,
    tier: int,
    hospital_level: int,
) -> datetime:
    """Never lengthen: min(current_eta, admission + new_total)."""
    candidate = fair_hospital_candidate_eta(
        admission=admission, tier=tier, hospital_level=hospital_level
    )
    return min(current_eta, candidate)


def should_early_discharge(*, now: datetime, final_eta: datetime) -> bool:
    return now >= final_eta


def fair_overflow_remaining_days(
    *,
    tier: int,
    injury_started_at: datetime | None,
    current_remaining: int,
    now: datetime,
) -> int:
    """
    min(current, max(0, ceil(base - elapsed_days))).
    Null start → elapsed 0 (full new untreated base, still never lengthen).
    """
    base = float(BASE_RECOVERY_DAYS.get(tier, 4))
    start = injury_started_at if injury_started_at is not None else now
    elapsed = max(0.0, (now - start).total_seconds() / 86400.0)
    remain = max(0, int(math.ceil(base - elapsed)))
    return min(max(0, int(current_remaining)), remain)


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
