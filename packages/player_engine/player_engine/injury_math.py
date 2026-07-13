# packages/player_engine/player_engine/injury_math.py
"""Post-match injury chance, tiers, hospital recovery (016 intensity-tier model)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence

from .intensity import clamp_intensity_tier

INJURY_ELIGIBLE_FATIGUE_BELOW = 75  # soft-cap C
INJURY_BASE_CHANCE = 0.0025  # Tier 1 default; prefer TIER_INJURY_BASE

TIER_MINOR = 1
TIER_MODERATE = 2
TIER_MAJOR = 3

TIER_NAMES = {1: "Minor", 2: "Moderate", 3: "Major"}

TIER_INJURY_BASE: dict[int, float] = {1: 0.0025, 2: 0.0040, 3: 0.0060}
MODERATE_BASE_DAYS: dict[int, int] = {1: 3, 2: 5, 3: 8}
SEVERITY_MULTIPLIER: dict[int, float] = {1: 0.33, 2: 1.0, 3: 2.5}

# Deprecated alias: untreated Moderate@Tier1 — prefer recovery_days_for_intensity
BASE_RECOVERY_DAYS = {1: 1, 2: 3, 3: 8}  # approximate Minor/Mod/Major @ T1 H0 for old callers


@dataclass(frozen=True)
class InjuryRollResult:
    player_card_id: str
    tier: int
    chance: float


def injury_chance(
    fatigue: int,
    age: int,
    phy: int,
    *,
    intensity_tier: int = 1,
) -> float:
    """Per-player injury probability (before A+C filters)."""
    base = TIER_INJURY_BASE[clamp_intensity_tier(intensity_tier)]
    fat_mod = (100 - fatigue) * 0.0003
    age_mod = max(0, (age - 30) * 0.0015)
    phy_mod = max(0, (phy - 70) * -0.0002)
    return max(0.0, base + fat_mod + age_mod + phy_mod)


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


def untreated_base_days(severity: int, intensity_tier: int) -> float:
    """Moderate_base × severity_mult (before hospital curve)."""
    moderate = float(MODERATE_BASE_DAYS[clamp_intensity_tier(intensity_tier)])
    sev = SEVERITY_MULTIPLIER.get(int(severity), 1.0)
    return moderate * sev


def recovery_days_for_intensity(
    severity: int,
    intensity_tier: int,
    hospital_level: int,
) -> int:
    raw = untreated_base_days(severity, intensity_tier) / (
        1.0 + 0.2 * max(0, int(hospital_level))
    )
    return max(1, int(math.ceil(raw)))


def recovery_days_for_tier(
    tier: int,
    hospital_level: int,
    *,
    intensity_tier: int = 1,
) -> int:
    """Severity = injury tier; intensity_tier defaults to 1 for legacy callers."""
    return recovery_days_for_intensity(tier, intensity_tier, hospital_level)


def new_total_recovery_days(
    tier: int,
    hospital_level: int,
    *,
    intensity_tier: int = 1,
) -> int:
    return recovery_days_for_intensity(tier, intensity_tier, hospital_level)


def fair_hospital_candidate_eta(
    *,
    admission: datetime,
    tier: int,
    hospital_level: int,
    intensity_tier: int = 1,
) -> datetime:
    days = new_total_recovery_days(tier, hospital_level, intensity_tier=intensity_tier)
    return admission + timedelta(days=days)


def fair_hospital_final_eta(
    *,
    admission: datetime,
    current_eta: datetime,
    tier: int,
    hospital_level: int,
    intensity_tier: int = 1,
) -> datetime:
    """Never lengthen: min(current_eta, admission + new_total)."""
    candidate = fair_hospital_candidate_eta(
        admission=admission,
        tier=tier,
        hospital_level=hospital_level,
        intensity_tier=intensity_tier,
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
    intensity_tier: int = 1,
) -> int:
    """
    min(current, max(0, ceil(untreated_base - elapsed_days))).
    Null start → elapsed 0.
    """
    base = untreated_base_days(tier, intensity_tier)
    start = injury_started_at if injury_started_at is not None else now
    elapsed = max(0.0, (now - start).total_seconds() / 86400.0)
    remain = max(0, int(math.ceil(base - elapsed)))
    return min(max(0, int(current_remaining)), remain)


def facility_bonus_pct(hospital_level: int) -> int:
    """Percent shorter vs untreated (for UI)."""
    mult = hospital_recovery_multiplier(hospital_level)
    return int(round((1.0 - mult) * 100))


def select_post_match_injury(
    starters: Sequence[dict[str, Any]],
    *,
    rng: random.Random | None = None,
    intensity_tier: int = 1,
) -> InjuryRollResult | None:
    """
    A+C soft-cap:
    - Only starters with fatigue < 75 are eligible (C).
    - At most one injury per club: first successful roll in starter order (A).
    """
    r = rng or random.Random()
    tier = clamp_intensity_tier(intensity_tier)
    for card in starters:
        fatigue = int(card.get("fatigue", 100))
        if fatigue >= INJURY_ELIGIBLE_FATIGUE_BELOW:
            continue
        card_id = str(card.get("id") or card.get("player_card_id") or "")
        if not card_id:
            continue
        age = int(card.get("age") or 25)
        phy = int(card.get("phy", 50))
        chance = injury_chance(fatigue, age, phy, intensity_tier=tier)
        if r.random() < chance:
            return InjuryRollResult(
                player_card_id=card_id,
                tier=roll_injury_tier(r),
                chance=chance,
            )
    return None
